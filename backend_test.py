#!/usr/bin/env python3
"""
Instagram Auto Poster Dashboard - Backend API Testing
Tests all backend APIs with real Instagram credentials provided by user.
"""

import requests
import json
import time
from datetime import datetime
import sys

# Backend URL from frontend/.env
BASE_URL = "https://e48bee04-5b24-44c9-9928-f3a352bd0b97.preview.emergentagent.com/api"

# Test credentials provided by user
TEST_CREDENTIALS = {
    "username": "badshitland",
    "password": "AEIOU@99.org"
}

# Test data
TEST_SOURCE_ACCOUNTS = ["natgeo", "bbcearth", "nationalgeographic"]

class BackendTester:
    def __init__(self):
        self.test_results = []
        self.added_accounts = []
        self.created_tasks = []
        
    def log_test(self, test_name, success, message, details=None):
        """Log test results"""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "details": details
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        if details:
            print(f"   Details: {details}")
        print()

    def test_server_health(self):
        """Test if the server is running and accessible"""
        try:
            response = requests.get(f"{BASE_URL}/", timeout=10)
            if response.status_code == 200:
                self.log_test("Server Health Check", True, "Server is running and accessible")
                return True
            else:
                self.log_test("Server Health Check", False, f"Server returned status {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Server Health Check", False, f"Cannot connect to server: {str(e)}")
            return False

    def test_accounts_list_empty(self):
        """Test accounts list when empty"""
        try:
            response = requests.get(f"{BASE_URL}/accounts/list", timeout=10)
            if response.status_code == 200:
                accounts = response.json()
                self.log_test("Accounts List (Empty)", True, f"Retrieved {len(accounts)} accounts", accounts)
                return True
            else:
                self.log_test("Accounts List (Empty)", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            self.log_test("Accounts List (Empty)", False, f"Error: {str(e)}")
            return False

    def test_add_instagram_account(self):
        """Test adding the real Instagram account"""
        try:
            payload = {
                "username": TEST_CREDENTIALS["username"],
                "password": TEST_CREDENTIALS["password"]
            }
            response = requests.post(f"{BASE_URL}/accounts/add", json=payload, timeout=10)
            
            if response.status_code == 200:
                self.added_accounts.append(TEST_CREDENTIALS["username"])
                self.log_test("Add Instagram Account", True, f"Successfully added @{TEST_CREDENTIALS['username']}")
                return True
            else:
                self.log_test("Add Instagram Account", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            self.log_test("Add Instagram Account", False, f"Error: {str(e)}")
            return False

    def test_duplicate_account_addition(self):
        """Test adding duplicate account (should fail)"""
        try:
            payload = {
                "username": TEST_CREDENTIALS["username"],
                "password": TEST_CREDENTIALS["password"]
            }
            response = requests.post(f"{BASE_URL}/accounts/add", json=payload, timeout=10)
            
            if response.status_code == 400:
                self.log_test("Duplicate Account Addition", True, "Correctly rejected duplicate account")
                return True
            else:
                self.log_test("Duplicate Account Addition", False, f"Expected 400, got {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Duplicate Account Addition", False, f"Error: {str(e)}")
            return False

    def test_accounts_list_with_data(self):
        """Test accounts list after adding account"""
        try:
            response = requests.get(f"{BASE_URL}/accounts/list", timeout=10)
            if response.status_code == 200:
                accounts = response.json()
                found_account = any(acc["username"] == TEST_CREDENTIALS["username"] for acc in accounts)
                if found_account:
                    self.log_test("Accounts List (With Data)", True, f"Found added account in list of {len(accounts)} accounts")
                    return True
                else:
                    self.log_test("Accounts List (With Data)", False, f"Added account not found in list", accounts)
                    return False
            else:
                self.log_test("Accounts List (With Data)", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            self.log_test("Accounts List (With Data)", False, f"Error: {str(e)}")
            return False

    def test_create_task(self):
        """Test creating a task with multiple source accounts"""
        try:
            payload = {
                "name": "Nature Content Monitor",
                "sourceUsername": TEST_SOURCE_ACCOUNTS,
                "destinationAccounts": [TEST_CREDENTIALS["username"]],
                "contentTypes": {
                    "photos": True,
                    "videos": True,
                    "stories": False
                }
            }
            response = requests.post(f"{BASE_URL}/tasks/add", json=payload, timeout=10)
            
            if response.status_code == 200:
                self.log_test("Create Task", True, "Successfully created task with multiple source accounts")
                return True
            else:
                self.log_test("Create Task", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            self.log_test("Create Task", False, f"Error: {str(e)}")
            return False

    def test_tasks_list(self):
        """Test listing tasks"""
        try:
            response = requests.get(f"{BASE_URL}/tasks/list", timeout=10)
            if response.status_code == 200:
                tasks = response.json()
                if len(tasks) > 0:
                    task = tasks[0]
                    self.created_tasks.append(task["id"])
                    self.log_test("Tasks List", True, f"Retrieved {len(tasks)} tasks", {"first_task_id": task["id"]})
                    return True
                else:
                    self.log_test("Tasks List", False, "No tasks found after creation")
                    return False
            else:
                self.log_test("Tasks List", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            self.log_test("Tasks List", False, f"Error: {str(e)}")
            return False

    def test_task_toggle(self):
        """Test toggling task enable/disable"""
        if not self.created_tasks:
            self.log_test("Task Toggle", False, "No tasks available to toggle")
            return False
            
        try:
            task_id = self.created_tasks[0]
            
            # Disable task
            payload = {"taskId": task_id, "enabled": False}
            response = requests.post(f"{BASE_URL}/tasks/toggle", json=payload, timeout=10)
            
            if response.status_code != 200:
                self.log_test("Task Toggle", False, f"Failed to disable task: {response.status_code}, {response.text}")
                return False
            
            # Enable task
            payload = {"taskId": task_id, "enabled": True}
            response = requests.post(f"{BASE_URL}/tasks/toggle", json=payload, timeout=10)
            
            if response.status_code == 200:
                self.log_test("Task Toggle", True, "Successfully toggled task enable/disable")
                return True
            else:
                self.log_test("Task Toggle", False, f"Failed to enable task: {response.status_code}, {response.text}")
                return False
        except Exception as e:
            self.log_test("Task Toggle", False, f"Error: {str(e)}")
            return False

    def test_manual_task_execution(self):
        """Test manual task execution"""
        if not self.created_tasks:
            self.log_test("Manual Task Execution", False, "No tasks available to execute")
            return False
            
        try:
            task_id = self.created_tasks[0]
            payload = {"taskId": task_id}
            response = requests.post(f"{BASE_URL}/tasks/run", json=payload, timeout=10)
            
            if response.status_code == 200:
                self.log_test("Manual Task Execution", True, "Successfully executed task manually")
                return True
            else:
                self.log_test("Manual Task Execution", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            self.log_test("Manual Task Execution", False, f"Error: {str(e)}")
            return False

    def test_logs_system(self):
        """Test logging system"""
        try:
            response = requests.get(f"{BASE_URL}/logs", timeout=10)
            if response.status_code == 200:
                logs = response.json()
                if len(logs) > 0:
                    # Check if we have logs from our test actions
                    account_add_log = any("Added Instagram account" in log.get("message", "") for log in logs)
                    task_log = any("Created task" in log.get("message", "") for log in logs)
                    
                    if account_add_log and task_log:
                        self.log_test("Logs System", True, f"Retrieved {len(logs)} logs with expected entries")
                        return True
                    else:
                        self.log_test("Logs System", False, f"Retrieved {len(logs)} logs but missing expected entries")
                        return False
                else:
                    self.log_test("Logs System", False, "No logs found despite performing actions")
                    return False
            else:
                self.log_test("Logs System", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            self.log_test("Logs System", False, f"Error: {str(e)}")
            return False

    def test_invalid_task_operations(self):
        """Test invalid task operations"""
        try:
            # Test running non-existent task
            payload = {"taskId": "non-existent-task-id"}
            response = requests.post(f"{BASE_URL}/tasks/run", json=payload, timeout=10)
            
            if response.status_code == 404:
                self.log_test("Invalid Task Operations", True, "Correctly handled non-existent task execution")
                return True
            else:
                self.log_test("Invalid Task Operations", False, f"Expected 404, got {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Invalid Task Operations", False, f"Error: {str(e)}")
            return False

    def test_create_task_with_invalid_destination(self):
        """Test creating task with non-existent destination account"""
        try:
            payload = {
                "name": "Invalid Destination Test",
                "sourceUsername": ["testaccount"],
                "destinationAccounts": ["nonexistent_account"],
                "contentTypes": {"photos": True}
            }
            response = requests.post(f"{BASE_URL}/tasks/add", json=payload, timeout=10)
            
            if response.status_code == 400:
                self.log_test("Invalid Destination Account", True, "Correctly rejected task with non-existent destination")
                return True
            else:
                self.log_test("Invalid Destination Account", False, f"Expected 400, got {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Invalid Destination Account", False, f"Error: {str(e)}")
            return False

    def test_remove_account(self):
        """Test removing Instagram account"""
        if not self.added_accounts:
            self.log_test("Remove Account", False, "No accounts to remove")
            return False
            
        try:
            payload = {"username": self.added_accounts[0]}
            response = requests.post(f"{BASE_URL}/accounts/remove", json=payload, timeout=10)
            
            if response.status_code == 200:
                self.log_test("Remove Account", True, f"Successfully removed @{self.added_accounts[0]}")
                return True
            else:
                self.log_test("Remove Account", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            self.log_test("Remove Account", False, f"Error: {str(e)}")
            return False

    def test_remove_nonexistent_account(self):
        """Test removing non-existent account"""
        try:
            payload = {"username": "definitely_not_existing_account"}
            response = requests.post(f"{BASE_URL}/accounts/remove", json=payload, timeout=10)
            
            if response.status_code == 404:
                self.log_test("Remove Non-existent Account", True, "Correctly handled non-existent account removal")
                return True
            else:
                self.log_test("Remove Non-existent Account", False, f"Expected 404, got {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Remove Non-existent Account", False, f"Error: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all backend tests in sequence"""
        print("=" * 80)
        print("INSTAGRAM AUTO POSTER DASHBOARD - BACKEND API TESTING")
        print("=" * 80)
        print(f"Testing against: {BASE_URL}")
        print(f"Test credentials: @{TEST_CREDENTIALS['username']}")
        print("=" * 80)
        print()

        # Test sequence
        tests = [
            ("Server Health Check", self.test_server_health),
            ("Initial Accounts List", self.test_accounts_list_empty),
            ("Add Instagram Account", self.test_add_instagram_account),
            ("Duplicate Account Addition", self.test_duplicate_account_addition),
            ("Accounts List With Data", self.test_accounts_list_with_data),
            ("Create Task", self.test_create_task),
            ("Tasks List", self.test_tasks_list),
            ("Task Toggle", self.test_task_toggle),
            ("Manual Task Execution", self.test_manual_task_execution),
            ("Logs System", self.test_logs_system),
            ("Invalid Task Operations", self.test_invalid_task_operations),
            ("Invalid Destination Account", self.test_create_task_with_invalid_destination),
            ("Remove Non-existent Account", self.test_remove_nonexistent_account),
            ("Remove Account", self.test_remove_account),
        ]

        passed = 0
        failed = 0

        for test_name, test_func in tests:
            try:
                if test_func():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                self.log_test(test_name, False, f"Test execution error: {str(e)}")
                failed += 1
            
            # Small delay between tests
            time.sleep(0.5)

        # Summary
        print("=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {passed + failed}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {(passed / (passed + failed) * 100):.1f}%")
        print("=" * 80)

        # Detailed results
        if failed > 0:
            print("\nFAILED TESTS:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"❌ {result['test']}: {result['message']}")
        
        return passed, failed

if __name__ == "__main__":
    tester = BackendTester()
    passed, failed = tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)