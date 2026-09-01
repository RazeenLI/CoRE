import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from baselines.embdi.model.matcher import build_embdi_graph, train_graph_embeddings
from baselines.santos.model.matcher import SantosMatcher
from baselines.starmie.model.matcher import resolve_required_path


def column(column_type="text"):
    return {"type": column_type, "nullable": False}


class SantosMatcherTest(unittest.TestCase):
    def test_prefers_existing_table_with_shared_column_semantics(self):
        matcher = SantosMatcher({"assignment_threshold": 0.20, "relationship_weight": 0.0})
        result = matcher(
            incoming_schema={"tables": {"Incoming": {"columns": {"City": column(), "Country": column()}}}},
            incoming_values=[{"City": "Paris", "Country": "France"}],
            existing_schema={"tables": {
                "Place": {"columns": {"Name": column(), "Nation": column()}},
                "Music": {"columns": {"Artist": column(), "Album": column()}},
            }},
            existing_values={
                "Place": [{"Name": "Paris", "Nation": "France"}],
                "Music": [{"Artist": "Miles Davis", "Album": "Kind of Blue"}],
            },
        )
        self.assertEqual(result["table_matches"][0]["target_table"], "Place")
        self.assertGreater(result["table_matches"][0]["confidence"], 0.9)


class EmbDITrainingTest(unittest.TestCase):
    def test_case_local_training_produces_column_vectors(self):
        graph, columns = build_embdi_graph([
            ("incoming", ["City"], [{"City": "Paris"}, {"City": "London"}]),
            ("Place", ["Name"], [{"Name": "Paris"}, {"Name": "London"}]),
        ])
        vectors = train_graph_embeddings(
            graph=graph,
            dimensions=8,
            walk_length=6,
            walks_per_node=2,
            window_size=2,
            epochs=1,
            negative_samples=2,
            learning_rate=0.025,
            batch_size=64,
            max_training_pairs=5000,
            seed=0,
            device="cpu",
        )
        self.assertIn(columns[("incoming", "City")], vectors)
        self.assertIn(columns[("Place", "Name")], vectors)


class StarmieAdapterTest(unittest.TestCase):
    def test_external_paths_are_resolved_without_importing_upstream_code(self):
        with TemporaryDirectory() as directory:
            resolved = resolve_required_path(
                directory,
                environment_name="AIRDB_TEST_UNUSED_PATH",
                description="test checkout",
            )
            self.assertEqual(resolved, Path(directory).resolve())


if __name__ == "__main__":
    unittest.main()
