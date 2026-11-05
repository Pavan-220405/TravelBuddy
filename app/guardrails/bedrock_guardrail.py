import os
import boto3

from dotenv import load_dotenv

load_dotenv()


class BedrockGuardrail:

    def __init__(self):

        self.client = boto3.client(
            "bedrock-runtime",
            region_name=os.getenv("AWS_DEFAULT_REGION")
        )

        self.guardrail_id = os.getenv("BEDROCK_GUARDRAIL_ID")
        self.guardrail_version = os.getenv("BEDROCK_GUARDRAIL_VERSION")

    def check(self, query: str, source: str = "INPUT") -> dict:

        response = self.client.apply_guardrail(
            guardrailIdentifier=self.guardrail_id,
            guardrailVersion=self.guardrail_version,
            source=source,
            content=[
                {
                    "text": {
                        "text": query
                    }
                }
            ],
            outputScope="FULL"
        )

        assessments = response.get("assessments", [])

        # Find whether any policy explicitly blocked the content.
        def find_actions(data, target):
            if isinstance(data, dict):
                found = data.get("action") == target
                return found or any(
                    find_actions(value, target)
                    for value in data.values()
                )

            if isinstance(data, list):
                return any(
                    find_actions(item, target)
                    for item in data
                )

            return False

        blocked = find_actions(assessments, "BLOCKED")
        anonymized = find_actions(assessments, "ANONYMIZED")

        outputs = response.get("outputs", [])

        # If Bedrock masked PII, use the returned sanitized text.
        checked_query = (
            outputs[0]["text"]
            if outputs and anonymized and not blocked
            else query
        )

        return {
            "allowed": not blocked,
            "action": response["action"],
            "action_reason": response.get("actionReason"),
            "original_query": query,
            "checked_query": checked_query,
            "blocked": blocked,
            "anonymized": anonymized,
            "outputs": outputs,
            "assessments": assessments,
            "usage": response.get("usage", {}),
            "raw_response": response
        }