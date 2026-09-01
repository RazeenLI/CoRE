from __future__ import annotations

import argparse
import random
import sys
import tempfile
from argparse import Namespace
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train one Starmie checkpoint in the current AIRDB environment."
    )
    parser.add_argument("--upstream-path", required=True)
    parser.add_argument("--data-path", required=True, help="Directory containing external VizNet CSV tables.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=5e-5)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--size", type=int, default=10000)
    parser.add_argument("--projector", type=int, default=768)
    parser.add_argument("--augment-op", default="drop_col")
    parser.add_argument("--sample-method", default="head")
    parser.add_argument("--table-order", default="column")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--no-amp", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    upstream_path = Path(args.upstream_path).expanduser().resolve()
    data_path = Path(args.data_path).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    if not (upstream_path / "sdd" / "model.py").is_file():
        raise FileNotFoundError(f"Official Starmie checkout not found: {upstream_path}")
    if not data_path.is_dir():
        raise FileNotFoundError(f"VizNet table directory not found: {data_path}")
    if str(upstream_path) not in sys.path:
        sys.path.insert(0, str(upstream_path))

    import numpy as np
    import torch
    from sdd.dataset import PretrainTableDataset
    from sdd.model import BarlowTwinsSimCLR

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested for Starmie training but is unavailable.")
    hp = Namespace(
        task="viznet",
        logdir=str(output_path.parent),
        run_id=args.seed,
        batch_size=args.batch_size,
        max_len=args.max_length,
        size=args.size,
        lr=args.learning_rate,
        n_epochs=args.epochs,
        lm="roberta",
        projector=args.projector,
        augment_op=args.augment_op,
        save_model=True,
        fp16=not args.no_amp,
        single_column=False,
        table_order=args.table_order,
        sample_meth=args.sample_method,
        mlflow_tag=None,
        scale_loss=0.025,
        lambd=0.005,
    )
    temporary_directory = None
    csv_files = sorted(
        path for path in data_path.rglob("*")
        if path.is_file() and not any(part.endswith("_multi-col") for part in path.parts)
    )
    if not csv_files:
        raise ValueError(f"No VizNet tables found recursively under: {data_path}")
    selection_rng = random.Random(args.seed)
    selection_rng.shuffle(csv_files)
    selected_files = csv_files[:args.size]
    temporary_directory = tempfile.TemporaryDirectory(prefix="airdb_viznet_flat_")
    flat_path = Path(temporary_directory.name)
    for index, source in enumerate(selected_files):
        (flat_path / f"table_{index:07d}.csv").symlink_to(source)
    training_path = flat_path
    trainset = PretrainTableDataset.from_hp(str(training_path), hp)
    loader = torch.utils.data.DataLoader(
        trainset,
        batch_size=hp.batch_size,
        shuffle=True,
        num_workers=0,
        collate_fn=trainset.pad,
    )
    model = BarlowTwinsSimCLR(hp, device=str(device), lm=hp.lm).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=hp.lr)
    total_steps = max(1, len(loader) * hp.n_epochs)
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer,
        lambda step: max(0.0, 1.0 - step / total_steps),
    )
    amp_enabled = hp.fp16 and device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=amp_enabled)

    for epoch in range(1, hp.n_epochs + 1):
        model.train()
        for step, (original, augmented, cls_indices) in enumerate(loader, start=1):
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast(device_type=device.type, enabled=amp_enabled):
                loss = model(original, augmented, cls_indices, mode="simclr")
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            if step == 1 or step % 10 == 0:
                print(
                    f"epoch={epoch}/{hp.n_epochs} step={step}/{len(loader)} "
                    f"loss={loss.item():.6f}",
                    flush=True,
                )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"model": model.state_dict(), "hp": hp}, output_path)
    if temporary_directory is not None:
        temporary_directory.cleanup()
    print(f"Saved Starmie checkpoint: {output_path}", flush=True)


if __name__ == "__main__":
    main()
