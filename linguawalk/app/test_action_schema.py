import unittest

from action_schema import ACTION_OPERATIONS, build_action_schema, validate_public_server_url


class ActionSchemaTests(unittest.TestCase):
    def test_exports_only_named_learning_operations(self) -> None:
        schema = build_action_schema("https://linguawalk.example.com")

        self.assertEqual(schema["servers"], [{"url": "https://linguawalk.example.com"}])
        self.assertEqual(set(schema["paths"]), set(ACTION_OPERATIONS))
        self.assertNotIn("/health", schema["paths"])

        operation_ids = {
            operation["operationId"]
            for path_item in schema["paths"].values()
            for operation in path_item.values()
        }
        self.assertEqual(
            operation_ids,
            {
                "startSession",
                "endSession",
                "getLearnerProfile",
                "getLearningProgress",
                "getLearningTargets",
                "recordVocabularyEvent",
                "recordGrammarEvent",
            },
        )

    def test_documents_bearer_auth_and_low_impact_writes(self) -> None:
        schema = build_action_schema("https://linguawalk.example.com/")

        self.assertEqual(
            schema["components"]["securitySchemes"]["bearerAuth"]["scheme"],
            "bearer",
        )
        for path_item in schema["paths"].values():
            for method, operation in path_item.items():
                self.assertEqual(operation["security"], [{"bearerAuth": []}])
                if method == "post":
                    self.assertIs(operation["x-openai-isConsequential"], False)
                self.assertLessEqual(len(operation["summary"]), 300)
                self.assertLessEqual(len(operation["description"]), 300)

    def test_rejects_non_public_or_nonstandard_servers(self) -> None:
        rejected = (
            "http://linguawalk.example.com",
            "https://linguawalk.example.invalid",
            "https://service.local",
            "https://localhost",
            "https://198.51.100.11",
            "https://linguawalk.example.com:8443",
            "https://user:secret@linguawalk.example.com",
            "https://linguawalk.example.com?token=secret",
        )
        for value in rejected:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_public_server_url(value)


if __name__ == "__main__":
    unittest.main()
