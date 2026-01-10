"""
CRM Integration Tests - Full Client Lifecycle
Tests: Onboarding -> Visa Application -> Status Changes
"""

import asyncio
from datetime import datetime
from typing import Any, Dict


class CRMClientLifecycleTest:
    """Test complete client lifecycle from onboarding to visa application"""

    def __init__(self, base_url: str, auth_token: str):
        self.base_url = base_url
        self.auth_token = auth_token
        self.client_data = {}
        self.created_client_id = None

    async def test_full_lifecycle(self) -> Dict[str, Any]:
        """
        Test complete client lifecycle:
        1. Client Onboarding
        2. Document Upload
        3. Visa Application Start
        4. Status Progression
        5. Completion/Rejection
        """
        results = {
            "test_name": "CRM Client Lifecycle",
            "start_time": datetime.now(),
            "steps": [],
            "success": True,
            "errors": [],
        }

        try:
            # Step 1: Client Onboarding
            onboarding_result = await self.test_client_onboarding()
            results["steps"].append(onboarding_result)

            # Step 2: Document Collection
            doc_result = await self.test_document_collection()
            results["steps"].append(doc_result)

            # Step 3: Visa Application
            visa_result = await self.test_visa_application()
            results["steps"].append(visa_result)

            # Step 4: Status Progression
            status_result = await self.test_status_progression()
            results["steps"].append(status_result)

            # Step 5: Completion
            completion_result = await self.test_completion()
            results["steps"].append(completion_result)

        except Exception as e:
            results["success"] = False
            results["errors"].append(str(e))

        results["end_time"] = datetime.now()
        results["duration"] = (results["end_time"] - results["start_time"]).total_seconds()

        return results

    async def test_client_onboarding(self) -> Dict[str, Any]:
        """Test client onboarding process"""
        step_result = {
            "step": "Client Onboarding",
            "start_time": datetime.now(),
            "success": True,
            "data": {},
            "errors": [],
        }

        try:
            # Create client
            client_payload = {
                "full_name": "Test Integration Client",
                "email": "test.integration@example.com",
                "phone": "+1234567890",
                "nationality": "IT",
                "passport_number": "IT123456789",
                "passport_expiry": "2025-12-31",
                "date_of_birth": "1990-01-01",
                "status": "prospect",
                "client_type": "individual",
                "assigned_to": "test@balizero.com",
                "tags": ["integration-test"],
                "lead_source": "website",
                "service_interest": ["visa_application"],
            }

            # API call to create client
            response = await self._make_request("POST", "/api/crm/clients", client_payload)

            if response.status_code == 200:
                client_data = response.json()
                self.created_client_id = client_data["id"]
                self.client_data = client_data

                step_result["data"] = {
                    "client_id": client_data["id"],
                    "uuid": client_data["uuid"],
                    "status": client_data["status"],
                    "created_at": client_data["created_at"],
                }

                # Verify client was created correctly
                assert client_data["full_name"] == client_payload["full_name"]
                assert client_data["email"] == client_payload["email"]
                assert client_data["status"] == "prospect"

            else:
                raise Exception(
                    f"Failed to create client: {response.status_code} - {response.text}"
                )

        except Exception as e:
            step_result["success"] = False
            step_result["errors"].append(str(e))

        step_result["end_time"] = datetime.now()
        step_result["duration"] = (
            step_result["end_time"] - step_result["start_time"]
        ).total_seconds()

        return step_result

    async def test_document_collection(self) -> Dict[str, Any]:
        """Test document collection phase"""
        step_result = {
            "step": "Document Collection",
            "start_time": datetime.now(),
            "success": True,
            "data": {},
            "errors": [],
        }

        try:
            # Update client status to active (documents collected)
            update_payload = {
                "status": "active",
                "notes": "Integration test: Documents collected and verified",
                "tags": ["integration-test", "documents-complete"],
            }

            response = await self._make_request(
                "PUT", f"/api/crm/clients/{self.created_client_id}", update_payload
            )

            if response.status_code == 200:
                updated_client = response.json()
                step_result["data"] = {
                    "status": updated_client["status"],
                    "updated_at": updated_client["updated_at"],
                    "notes": updated_client.get("notes", ""),
                }

                assert updated_client["status"] == "active"

            else:
                raise Exception(f"Failed to update client: {response.status_code}")

        except Exception as e:
            step_result["success"] = False
            step_result["errors"].append(str(e))

        step_result["end_time"] = datetime.now()
        step_result["duration"] = (
            step_result["end_time"] - step_result["start_time"]
        ).total_seconds()

        return step_result

    async def test_visa_application(self) -> Dict[str, Any]:
        """Test visa application initiation"""
        step_result = {
            "step": "Visa Application",
            "start_time": datetime.now(),
            "success": True,
            "data": {},
            "errors": [],
        }

        try:
            # Create visa application case
            case_payload = {
                "client_id": self.created_client_id,
                "case_type": "visa_application",
                "visa_type": "work_visa",
                "destination_country": "IT",
                "priority": "normal",
                "assigned_to": "test@balizero.com",
                "description": "Integration test visa application",
            }

            response = await self._make_request("POST", "/api/crm/cases", case_payload)

            if response.status_code == 200:
                case_data = response.json()
                step_result["data"] = {
                    "case_id": case_data["id"],
                    "case_type": case_data["case_type"],
                    "status": case_data["status"],
                    "created_at": case_data["created_at"],
                }

                # Update client with case reference
                client_update = {
                    "service_interest": ["visa_application"],
                    "custom_fields": {
                        "current_case_id": case_data["id"],
                        "application_date": datetime.now().isoformat(),
                    },
                }

                client_response = await self._make_request(
                    "PUT", f"/api/crm/clients/{self.created_client_id}", client_update
                )

                if client_response.status_code != 200:
                    raise Exception("Failed to update client with case reference")

            else:
                raise Exception(f"Failed to create case: {response.status_code}")

        except Exception as e:
            step_result["success"] = False
            step_result["errors"].append(str(e))

        step_result["end_time"] = datetime.now()
        step_result["duration"] = (
            step_result["end_time"] - step_result["start_time"]
        ).total_seconds()

        return step_result

    async def test_status_progression(self) -> Dict[str, Any]:
        """Test status progression through application lifecycle"""
        step_result = {
            "step": "Status Progression",
            "start_time": datetime.now(),
            "success": True,
            "data": {},
            "errors": [],
        }

        try:
            status_progression = [
                ("active", "Application submitted"),
                ("active", "Under review"),
                ("active", "Additional documents requested"),
                ("active", "Final review"),
                ("active", "Approved"),
            ]

            progression_data = []

            for i, (status, note) in enumerate(status_progression):
                update_payload = {
                    "notes": f"Integration test step {i + 1}: {note}",
                    "custom_fields": {
                        "last_status_change": datetime.now().isoformat(),
                        "progress_step": i + 1,
                    },
                }

                response = await self._make_request(
                    "PUT", f"/api/crm/clients/{self.created_client_id}", update_payload
                )

                if response.status_code == 200:
                    updated_client = response.json()
                    progression_data.append(
                        {
                            "step": i + 1,
                            "status": updated_client["status"],
                            "updated_at": updated_client["updated_at"],
                            "note": note,
                        }
                    )
                else:
                    raise Exception(f"Failed status progression step {i + 1}")

            step_result["data"] = {
                "progression_steps": len(progression_data),
                "final_status": progression_data[-1]["status"] if progression_data else None,
                "progression": progression_data,
            }

        except Exception as e:
            step_result["success"] = False
            step_result["errors"].append(str(e))

        step_result["end_time"] = datetime.now()
        step_result["duration"] = (
            step_result["end_time"] - step_result["start_time"]
        ).total_seconds()

        return step_result

    async def test_completion(self) -> Dict[str, Any]:
        """Test final completion/closure"""
        step_result = {
            "step": "Completion",
            "start_time": datetime.now(),
            "success": True,
            "data": {},
            "errors": [],
        }

        try:
            # Mark as completed
            completion_payload = {
                "status": "inactive",
                "notes": "Integration test: Visa application completed successfully",
                "tags": ["integration-test", "completed"],
                "custom_fields": {
                    "completion_date": datetime.now().isoformat(),
                    "outcome": "approved",
                },
            }

            response = await self._make_request(
                "PUT", f"/api/crm/clients/{self.created_client_id}", completion_payload
            )

            if response.status_code == 200:
                final_client = response.json()
                step_result["data"] = {
                    "final_status": final_client["status"],
                    "completed_at": final_client["updated_at"],
                    "outcome": final_client.get("custom_fields", {}).get("outcome"),
                }

                # Verify final state
                assert final_client["status"] == "inactive"
                assert "completed" in final_client.get("tags", [])

            else:
                raise Exception(f"Failed to complete client: {response.status_code}")

        except Exception as e:
            step_result["success"] = False
            step_result["errors"].append(str(e))

        step_result["end_time"] = datetime.now()
        step_result["duration"] = (
            step_result["end_time"] - step_result["start_time"]
        ).total_seconds()

        return step_result

    async def _make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None) -> Any:
        """Make HTTP request to CRM API"""
        import httpx

        headers = {"Authorization": f"Bearer {self.auth_token}", "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            if method == "POST":
                response = await client.post(
                    f"{self.base_url}{endpoint}", json=data, headers=headers
                )
            elif method == "PUT":
                response = await client.put(
                    f"{self.base_url}{endpoint}", json=data, headers=headers
                )
            elif method == "GET":
                response = await client.get(f"{self.base_url}{endpoint}", headers=headers)

            return response


# Test runner
async def run_crm_integration_tests(base_url: str, auth_token: str) -> Dict[str, Any]:
    """Run all CRM integration tests"""
    test_suite = CRMClientLifecycleTest(base_url, auth_token)
    results = await test_suite.test_full_lifecycle()

    # Generate test report
    report = {
        "test_suite": "CRM Client Lifecycle Integration Tests",
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "summary": {
            "total_steps": len(results["steps"]),
            "successful_steps": len([s for s in results["steps"] if s["success"]]),
            "failed_steps": len([s for s in results["steps"] if not s["success"]]),
            "total_duration": results["duration"],
            "success_rate": len([s for s in results["steps"] if s["success"]])
            / len(results["steps"])
            * 100,
        },
    }

    return report


if __name__ == "__main__":
    # Example usage
    import asyncio

    async def main():
        base_url = "https://nuzantara-rag.fly.dev"
        auth_token = "your-auth-token-here"

        report = await run_crm_integration_tests(base_url, auth_token)
        print(f"Test Results: {report}")

    asyncio.run(main())
