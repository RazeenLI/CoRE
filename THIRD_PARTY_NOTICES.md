# Third-party components and research systems

The MIT license in this repository covers CoRE's original project code. It does
not replace licenses for installed dependencies, upstream implementations,
models, checkpoints, datasets, or papers.

## Runtime dependencies

PyTorch, Transformers, Sentence Transformers, NumPy, Pandas, SciPy, PyYAML,
Matplotlib, pytest, and Valentine are installed as external packages and remain
under their respective upstream licenses. Their source code is not vendored in
this repository.

## Adapted research baselines

- **EmbDI:** this repository contains an independent adaptation of the
  heterogeneous-graph, random-walk, and embedding approach. The upstream
  implementation is available at <https://github.com/rcap107/embdi> and is
  identified upstream as Apache-2.0.
- **SANTOS:** this repository contains an adaptation of the synthesized-KB
  approach. The upstream implementation is available at
  <https://github.com/northeastern-datalab/santos> and is identified in the
  baseline documentation as BSD-3-Clause.
- **Magneto:** the baseline follows the retrieval/reranking roles described by
  the Magneto paper but uses CoRE-specific implementation and proposal
  conversion. See <https://github.com/VIDA-NYU/magneto-matcher> and verify the
  upstream repository license before copying any upstream code.
- **Starmie:** upstream source and checkpoints are not redistributed because
  the upstream repository did not declare a software license during this
  audit. Users prepare them externally from
  <https://github.com/megagonlabs/starmie>.
- **Valentine / COMA / JL:** CoRE calls the separately installed Valentine
  package for these matchers. See <https://github.com/delftdata/valentine>.

These systems do not natively produce CoRE database-evolution proposals. The
adapters in this repository convert their evidence to a shared evaluation
format; resulting metrics should be described as adapted end-to-end results.
