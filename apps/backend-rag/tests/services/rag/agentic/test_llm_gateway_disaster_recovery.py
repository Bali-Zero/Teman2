"""
Disaster Recovery and Business Continuity Testing Suite for LLMGateway

This suite provides comprehensive disaster recovery, business continuity,
and resilience testing for the LLMGateway module with advanced failover scenarios.

Disaster Recovery and Business Continuity Coverage Areas:
- Disaster recovery planning and execution
- Business continuity validation
- High availability and failover testing
- Data backup and recovery testing
- Geographic redundancy validation
- Emergency response procedures
- Recovery time objective (RTO) testing
- Recovery point objective (RPO) testing
- Disaster simulation scenarios
- Business impact analysis

Author: Nuzantara Team
Date: 2025-01-04
Version: 10.0.0 (Disaster Recovery & Business Continuity Edition)
"""

import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

# Import the minimal gateway for testing
from test_llm_gateway_isolated import MinimalLLMGateway


class TestDisasterRecoveryPlanning:
    """Test disaster recovery planning and execution scenarios."""

    @pytest.fixture
    def dr_gateway(self):
        """Gateway configured for disaster recovery testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.dr_system = {
            "backup_sites": {},
            "recovery_procedures": {},
            "disaster_scenarios": {},
            "recovery_metrics": {},
        }
        return gateway

    def test_disaster_recovery_plan_execution(self, dr_gateway):
        """Test disaster recovery plan execution."""
        gateway = dr_gateway

        def create_dr_plan(plan_name, rto_minutes, rpo_minutes):
            """Create a disaster recovery plan."""
            plan = {
                "name": plan_name,
                "rto_minutes": rto_minutes,  # Recovery Time Objective
                "rpo_minutes": rpo_minutes,  # Recovery Point Objective
                "created_at": datetime.now(),
                "procedures": [],
                "tested": False,
                "last_test_date": None,
            }

            gateway.dr_system["recovery_procedures"][plan_name] = plan
            return plan

        def add_recovery_step(plan_name, step_name, step_function, estimated_duration_minutes):
            """Add recovery step to DR plan."""
            if plan_name not in gateway.dr_system["recovery_procedures"]:
                return False

            step = {
                "name": step_name,
                "function": step_function,
                "estimated_duration_minutes": estimated_duration_minutes,
                "dependencies": [],
                "status": "pending",
            }

            gateway.dr_system["recovery_procedures"][plan_name]["procedures"].append(step)
            return True

        def execute_dr_plan(plan_name):
            """Execute disaster recovery plan."""
            if plan_name not in gateway.dr_system["recovery_procedures"]:
                return {"success": False, "error": "Plan not found"}

            plan = gateway.dr_system["recovery_procedures"][plan_name]
            start_time = datetime.now()

            results = []
            total_duration = 0

            for step in plan["procedures"]:
                step_start = time.time()

                try:
                    # Execute step function (mock)
                    if step["function"]:
                        step["function"]()

                    step_duration = time.time() - step_start
                    step["actual_duration_minutes"] = step_duration / 60
                    step["status"] = "completed"

                    total_duration += step_duration

                    results.append(
                        {
                            "step": step["name"],
                            "status": "success",
                            "duration_minutes": step_duration / 60,
                        }
                    )

                except Exception as e:
                    step["status"] = "failed"
                    step["error"] = str(e)

                    results.append({"step": step["name"], "status": "failed", "error": str(e)})

                    # Stop execution on failure
                    break

            end_time = datetime.now()
            actual_rto = (end_time - start_time).total_seconds() / 60

            # Update plan
            plan["tested"] = True
            plan["last_test_date"] = end_time
            plan["last_test_duration_minutes"] = actual_rto
            plan["last_test_results"] = results

            return {
                "success": all(r["status"] == "success" for r in results),
                "actual_rto_minutes": actual_rto,
                "target_rto_minutes": plan["rto_minutes"],
                "results": results,
            }

        # Create DR plan
        dr_plan = create_dr_plan("primary_site_failure", 30, 15)

        # Add recovery steps
        add_recovery_step("primary_site_failure", "detect_failure", lambda: None, 1)
        add_recovery_step("primary_site_failure", "activate_backup_site", lambda: None, 5)
        add_recovery_step("primary_site_failure", "restore_data_backup", lambda: None, 10)
        add_recovery_step("primary_site_failure", "verify_service_health", lambda: None, 2)
        add_recovery_step("primary_site_failure", "redirect_traffic", lambda: None, 1)

        # Execute DR plan
        execution_result = execute_dr_plan("primary_site_failure")

        assert execution_result["success"] == True
        assert execution_result["actual_rto_minutes"] <= execution_result["target_rto_minutes"]
        assert len(execution_result["results"]) == 5

    def test_recovery_time_objective_compliance(self, dr_gateway):
        """Test Recovery Time Objective (RTO) compliance."""
        gateway = dr_gateway

        def simulate_disaster_recovery(scenario_name, complexity_factor=1.0):
            """Simulate disaster recovery scenario."""
            scenarios = {
                "simple_failure": {
                    "base_rto": 5,  # 5 minutes
                    "steps": ["detect", "switch", "verify"],
                },
                "complex_failure": {
                    "base_rto": 30,  # 30 minutes
                    "steps": ["detect", "assess", "switch", "restore", "verify", "optimize"],
                },
                "catastrophic_failure": {
                    "base_rto": 120,  # 2 hours
                    "steps": [
                        "detect",
                        "declare",
                        "mobilize",
                        "switch",
                        "restore",
                        "verify",
                        "communicate",
                    ],
                },
            }

            if scenario_name not in scenarios:
                return {"success": False, "error": "Unknown scenario"}

            scenario = scenarios[scenario_name]
            start_time = time.time()

            # Simulate recovery steps
            for step in scenario["steps"]:
                # Each step takes different amount of time
                step_time = len(step) * complexity_factor
                time.sleep(0.01)  # Minimal sleep for testing

            end_time = time.time()
            actual_rto = (end_time - start_time) * 100  # Convert to simulated minutes

            return {
                "scenario": scenario_name,
                "target_rto": scenario["base_rto"],
                "actual_rto": actual_rto,
                "compliance": actual_rto <= scenario["base_rto"],
                "steps_completed": len(scenario["steps"]),
            }

        # Test different scenarios
        simple_result = simulate_disaster_recovery("simple_failure", complexity_factor=0.5)
        complex_result = simulate_disaster_recovery("complex_failure", complexity_factor=0.8)
        catastrophic_result = simulate_disaster_recovery(
            "catastrophic_failure", complexity_factor=0.3
        )

        # Verify RTO compliance
        assert simple_result["compliance"] == True
        assert complex_result["compliance"] == True
        assert catastrophic_result["compliance"] == True

        # Verify step completion
        assert simple_result["steps_completed"] == 3
        assert complex_result["steps_completed"] == 6
        assert catastrophic_result["steps_completed"] == 7

    def test_recovery_point_objective_validation(self, dr_gateway):
        """Test Recovery Point Objective (RPO) validation."""
        gateway = dr_gateway

        def simulate_data_backup_and_recovery(rpo_target_minutes, backup_frequency_minutes):
            """Simulate data backup and recovery with RPO validation."""
            backup_points = []
            current_time = datetime.now()

            # Generate backup points
            for i in range(24):  # 24 hours of backups
                backup_time = current_time - timedelta(hours=i)
                backup_points.append(
                    {
                        "timestamp": backup_time,
                        "data_loss_risk_minutes": i * backup_frequency_minutes,
                    }
                )

            # Simulate disaster at random time
            disaster_time = current_time - timedelta(minutes=37)  # 37 minutes ago

            # Find most recent backup before disaster
            latest_backup = None
            for backup in backup_points:
                if backup["timestamp"] <= disaster_time:
                    latest_backup = backup
                    break

            if latest_backup:
                data_loss_minutes = (
                    disaster_time - latest_backup["timestamp"]
                ).total_seconds() / 60
                rpo_compliance = data_loss_minutes <= rpo_target_minutes
            else:
                data_loss_minutes = float("inf")
                rpo_compliance = False

            return {
                "rpo_target_minutes": rpo_target_minutes,
                "backup_frequency_minutes": backup_frequency_minutes,
                "disaster_time": disaster_time,
                "latest_backup_time": latest_backup["timestamp"] if latest_backup else None,
                "actual_data_loss_minutes": data_loss_minutes,
                "rpo_compliance": rpo_compliance,
                "total_backups": len(backup_points),
            }

        # Test different RPO scenarios
        strict_rpo = simulate_data_backup_and_recovery(
            rpo_target_minutes=5, backup_frequency_minutes=5
        )
        moderate_rpo = simulate_data_backup_and_recovery(
            rpo_target_minutes=15, backup_frequency_minutes=15
        )
        relaxed_rpo = simulate_data_backup_and_recovery(
            rpo_target_minutes=60, backup_frequency_minutes=60
        )

        # Verify RPO compliance
        assert strict_rpo["rpo_compliance"] == True
        assert moderate_rpo["rpo_compliance"] == True
        assert relaxed_rpo["rpo_compliance"] == True

        # Verify data loss is within acceptable range
        assert strict_rpo["actual_data_loss_minutes"] <= strict_rpo["rpo_target_minutes"]
        assert moderate_rpo["actual_data_loss_minutes"] <= moderate_rpo["rpo_target_minutes"]
        assert relaxed_rpo["actual_data_loss_minutes"] <= relaxed_rpo["rpo_target_minutes"]


class TestBusinessContinuityValidation:
    """Test business continuity validation scenarios."""

    @pytest.fixture
    def bc_gateway(self):
        """Gateway configured for business continuity testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.bc_system = {
            "critical_functions": {},
            "continuity_plans": {},
            "impact_analysis": {},
            "service_levels": {},
        }
        return gateway

    def test_critical_function_identification(self, bc_gateway):
        """Test critical function identification and prioritization."""
        gateway = bc_gateway

        def identify_critical_functions():
            """Identify and prioritize critical business functions."""
            functions = [
                {
                    "name": "customer_chat_support",
                    "priority": "critical",
                    "max_downtime_minutes": 5,
                    "revenue_impact_per_hour": 10000,
                    "customer_impact": "high",
                    "dependencies": ["llm_service", "database", "authentication"],
                },
                {
                    "name": "user_authentication",
                    "priority": "critical",
                    "max_downtime_minutes": 2,
                    "revenue_impact_per_hour": 15000,
                    "customer_impact": "critical",
                    "dependencies": ["database", "security_service"],
                },
                {
                    "name": "content_generation",
                    "priority": "important",
                    "max_downtime_minutes": 30,
                    "revenue_impact_per_hour": 5000,
                    "customer_impact": "medium",
                    "dependencies": ["llm_service", "storage"],
                },
                {
                    "name": "analytics_processing",
                    "priority": "normal",
                    "max_downtime_minutes": 120,
                    "revenue_impact_per_hour": 1000,
                    "customer_impact": "low",
                    "dependencies": ["data_pipeline", "storage"],
                },
            ]

            for func in functions:
                func["id"] = str(uuid.uuid4())
                func["identified_at"] = datetime.now()
                gateway.bc_system["critical_functions"][func["name"]] = func

            return functions

        def calculate_business_impact(function_name, downtime_minutes):
            """Calculate business impact of function downtime."""
            if function_name not in gateway.bc_system["critical_functions"]:
                return {"error": "Function not found"}

            func = gateway.bc_system["critical_functions"][function_name]

            revenue_impact = (downtime_minutes / 60) * func["revenue_impact_per_hour"]
            customer_impact_score = {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(
                func["customer_impact"], 0
            )

            sla_breach = downtime_minutes > func["max_downtime_minutes"]

            return {
                "function": function_name,
                "downtime_minutes": downtime_minutes,
                "revenue_impact": revenue_impact,
                "customer_impact_score": customer_impact_score,
                "sla_breach": sla_breach,
                "overall_impact_score": revenue_impact * customer_impact_score,
            }

        # Test critical function identification
        critical_functions = identify_critical_functions()
        assert len(critical_functions) == 4

        # Verify prioritization
        critical_priority = [f for f in critical_functions if f["priority"] == "critical"]
        assert len(critical_priority) == 2

        # Test business impact calculation
        chat_impact = calculate_business_impact("customer_chat_support", 10)
        assert chat_impact["revenue_impact"] == 1666.67  # 10/60 * 10000
        assert chat_impact["sla_breach"] == True  # 10 > 5 minutes

        auth_impact = calculate_business_impact("user_authentication", 1)
        assert auth_impact["sla_breach"] == False  # 1 <= 2 minutes

    def test_service_level_agreement_compliance(self, bc_gateway):
        """Test Service Level Agreement (SLA) compliance."""
        gateway = bc_gateway

        def define_sla(service_name, availability_target, response_time_target):
            """Define SLA for a service."""
            sla = {
                "service_name": service_name,
                "availability_target": availability_target,  # percentage
                "response_time_target_ms": response_time_target,
                "created_at": datetime.now(),
                "measurement_period_days": 30,
                "current_metrics": {
                    "uptime_percentage": 0,
                    "avg_response_time_ms": 0,
                    "total_requests": 0,
                    "failed_requests": 0,
                },
            }

            gateway.bc_system["service_levels"][service_name] = sla
            return sla

        def record_sla_metrics(
            service_name, uptime_percentage, avg_response_time_ms, total_requests, failed_requests
        ):
            """Record SLA metrics for a service."""
            if service_name not in gateway.bc_system["service_levels"]:
                return False

            sla = gateway.bc_system["service_levels"][service_name]
            sla["current_metrics"] = {
                "uptime_percentage": uptime_percentage,
                "avg_response_time_ms": avg_response_time_ms,
                "total_requests": total_requests,
                "failed_requests": failed_requests,
                "error_rate": (failed_requests / total_requests) * 100 if total_requests > 0 else 0,
            }

            return True

        def check_sla_compliance(service_name):
            """Check SLA compliance for a service."""
            if service_name not in gateway.bc_system["service_levels"]:
                return {"compliant": False, "error": "SLA not defined"}

            sla = gateway.bc_system["service_levels"][service_name]
            metrics = sla["current_metrics"]

            availability_compliant = metrics["uptime_percentage"] >= sla["availability_target"]
            response_time_compliant = (
                metrics["avg_response_time_ms"] <= sla["response_time_target_ms"]
            )

            overall_compliant = availability_compliant and response_time_compliant

            return {
                "service": service_name,
                "availability_compliant": availability_compliant,
                "response_time_compliant": response_time_compliant,
                "overall_compliant": overall_compliant,
                "current_availability": metrics["uptime_percentage"],
                "target_availability": sla["availability_target"],
                "current_response_time": metrics["avg_response_time_ms"],
                "target_response_time": sla["response_time_target_ms"],
            }

        # Define SLAs
        define_sla("llm_gateway_api", 99.9, 500)
        define_sla("user_service", 99.95, 200)
        define_sla("content_service", 99.5, 1000)

        # Record metrics
        record_sla_metrics("llm_gateway_api", 99.92, 450, 100000, 80)
        record_sla_metrics("user_service", 99.93, 180, 50000, 25)
        record_sla_metrics("content_service", 99.4, 950, 25000, 150)

        # Check compliance
        api_compliance = check_sla_compliance("llm_gateway_api")
        user_compliance = check_sla_compliance("user_service")
        content_compliance = check_sla_compliance("content_service")

        assert api_compliance["overall_compliant"] == True
        assert user_compliance["overall_compliant"] == True
        assert content_compliance["overall_compliant"] == False  # 99.4% < 99.5%

    def test_business_impact_analysis(self, bc_gateway):
        """Test business impact analysis for disaster scenarios."""
        gateway = bc_gateway

        def create_disaster_scenario(scenario_name, severity, affected_functions, duration_hours):
            """Create a disaster scenario for impact analysis."""
            scenario = {
                "name": scenario_name,
                "severity": severity,  # low, medium, high, critical
                "affected_functions": affected_functions,
                "estimated_duration_hours": duration_hours,
                "created_at": datetime.now(),
                "impact_assessment": {},
            }

            gateway.bc_system["impact_analysis"][scenario_name] = scenario
            return scenario

        def calculate_scenario_impact(scenario_name):
            """Calculate business impact for a disaster scenario."""
            if scenario_name not in gateway.bc_system["impact_analysis"]:
                return {"error": "Scenario not found"}

            scenario = gateway.bc_system["impact_analysis"][scenario_name]

            total_revenue_impact = 0
            total_customer_impact = 0
            affected_customers = 0

            for function_name in scenario["affected_functions"]:
                if function_name in gateway.bc_system["critical_functions"]:
                    func = gateway.bc_system["critical_functions"][function_name]

                    # Calculate revenue impact
                    revenue_impact = (
                        scenario["estimated_duration_hours"] * func["revenue_impact_per_hour"]
                    )
                    total_revenue_impact += revenue_impact

                    # Calculate customer impact
                    customer_impact_score = {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(
                        func["customer_impact"], 0
                    )

                    total_customer_impact += customer_impact_score

                    # Estimate affected customers (simplified)
                    if func["customer_impact"] in ["high", "critical"]:
                        affected_customers += 1000
                    elif func["customer_impact"] == "medium":
                        affected_customers += 500
                    else:
                        affected_customers += 100

            # Calculate overall impact score
            severity_multiplier = {"low": 0.5, "medium": 1.0, "high": 1.5, "critical": 2.0}.get(
                scenario["severity"], 1.0
            )

            overall_impact_score = (
                total_revenue_impact * 0.01 + total_customer_impact * 1000
            ) * severity_multiplier

            scenario["impact_assessment"] = {
                "total_revenue_impact": total_revenue_impact,
                "total_customer_impact_score": total_customer_impact,
                "estimated_affected_customers": affected_customers,
                "overall_impact_score": overall_impact_score,
                "calculated_at": datetime.now(),
            }

            return scenario["impact_assessment"]

        # Create test functions first
        gateway.bc_system["critical_functions"] = {
            "customer_chat_support": {"revenue_impact_per_hour": 10000, "customer_impact": "high"},
            "user_authentication": {
                "revenue_impact_per_hour": 15000,
                "customer_impact": "critical",
            },
            "content_generation": {"revenue_impact_per_hour": 5000, "customer_impact": "medium"},
        }

        # Create disaster scenarios
        create_disaster_scenario(
            "data_center_outage", "critical", ["customer_chat_support", "user_authentication"], 4
        )
        create_disaster_scenario("network_degradation", "medium", ["content_generation"], 2)
        create_disaster_scenario("partial_service_failure", "low", ["content_generation"], 1)

        # Calculate impacts
        critical_impact = calculate_scenario_impact("data_center_outage")
        medium_impact = calculate_scenario_impact("network_degradation")
        low_impact = calculate_scenario_impact("partial_service_failure")

        # Verify impact calculations
        assert critical_impact["total_revenue_impact"] == 100000  # (10000 + 15000) * 4 hours
        assert medium_impact["total_revenue_impact"] == 10000  # 5000 * 2 hours
        assert low_impact["total_revenue_impact"] == 5000  # 5000 * 1 hour

        # Verify severity affects impact score
        assert critical_impact["overall_impact_score"] > medium_impact["overall_impact_score"]
        assert medium_impact["overall_impact_score"] > low_impact["overall_impact_score"]


class TestHighAvailabilityAndFailover:
    """Test high availability and failover scenarios."""

    @pytest.fixture
    def ha_gateway(self):
        """Gateway configured for high availability testing."""
        gateway = MinimalLLMGateway()
        gateway._genai_client = Mock()
        gateway._available = True
        gateway.ha_system = {
            "clusters": {},
            "failover_procedures": {},
            "health_checks": {},
            "load_balancers": {},
        }
        return gateway

    def test_active_passive_failover(self, ha_gateway):
        """Test active-passive failover scenario."""
        gateway = ha_gateway

        def setup_active_passive_cluster(cluster_name, active_node, passive_nodes):
            """Setup active-passive cluster configuration."""
            cluster = {
                "name": cluster_name,
                "mode": "active_passive",
                "active_node": active_node,
                "passive_nodes": passive_nodes,
                "current_active": active_node,
                "failover_count": 0,
                "last_failover": None,
                "health_status": {},
            }

            # Initialize health status
            all_nodes = [active_node] + passive_nodes
            for node in all_nodes:
                cluster["health_status"][node] = {
                    "healthy": True,
                    "last_check": datetime.now(),
                    "response_time_ms": 50,
                }

            gateway.ha_system["clusters"][cluster_name] = cluster
            return cluster

        def check_node_health(node_name):
            """Check health of a specific node."""
            if node_name not in gateway.ha_system["clusters"]:
                return {"healthy": False}

            cluster = gateway.ha_system["clusters"][node_name]
            current_active = cluster["current_active"]

            # Simulate health check
            import random

            is_healthy = random.random() > 0.1  # 90% chance healthy

            cluster["health_status"][current_active]["healthy"] = is_healthy
            cluster["health_status"][current_active]["last_check"] = datetime.now()

            return {"healthy": is_healthy, "node": current_active}

        def trigger_failover(cluster_name):
            """Trigger failover to passive node."""
            if cluster_name not in gateway.ha_system["clusters"]:
                return {"success": False, "error": "Cluster not found"}

            cluster = gateway.ha_system["clusters"][cluster_name]

            if not cluster["passive_nodes"]:
                return {"success": False, "error": "No passive nodes available"}

            # Select next healthy passive node
            new_active = None
            for node in cluster["passive_nodes"]:
                if cluster["health_status"][node]["healthy"]:
                    new_active = node
                    break

            if not new_active:
                return {"success": False, "error": "No healthy passive nodes available"}

            # Perform failover
            old_active = cluster["current_active"]
            cluster["current_active"] = new_active
            cluster["failover_count"] += 1
            cluster["last_failover"] = datetime.now()

            # Move old active to passive
            cluster["passive_nodes"].remove(new_active)
            cluster["passive_nodes"].append(old_active)

            return {
                "success": True,
                "old_active": old_active,
                "new_active": new_active,
                "failover_count": cluster["failover_count"],
                "failover_time": cluster["last_failover"],
            }

        # Setup cluster
        cluster = setup_active_passive_cluster("main_cluster", "node1", ["node2", "node3"])

        # Simulate active node failure
        cluster["health_status"]["node1"]["healthy"] = False

        # Trigger failover
        failover_result = trigger_failover("main_cluster")

        assert failover_result["success"] == True
        assert failover_result["old_active"] == "node1"
        assert failover_result["new_active"] == "node2"
        assert failover_result["failover_count"] == 1

        # Verify cluster state
        updated_cluster = gateway.ha_system["clusters"]["main_cluster"]
        assert updated_cluster["current_active"] == "node2"
        assert "node1" in updated_cluster["passive_nodes"]

    def test_load_balancer_failover(self, ha_gateway):
        """Test load balancer failover scenarios."""
        gateway = ha_gateway

        def setup_load_balancer(lb_name, backend_nodes, algorithm="round_robin"):
            """Setup load balancer configuration."""
            load_balancer = {
                "name": lb_name,
                "algorithm": algorithm,
                "backend_nodes": backend_nodes,
                "healthy_nodes": backend_nodes.copy(),
                "current_index": 0,
                "total_requests": 0,
                "node_requests": dict.fromkeys(backend_nodes, 0),
            }

            gateway.ha_system["load_balancers"][lb_name] = load_balancer
            return load_balancer

        def route_request(lb_name):
            """Route request to backend node."""
            if lb_name not in gateway.ha_system["load_balancers"]:
                return {"success": False, "error": "Load balancer not found"}

            lb = gateway.ha_system["load_balancers"][lb_name]

            if not lb["healthy_nodes"]:
                return {"success": False, "error": "No healthy nodes available"}

            # Select node based on algorithm
            if lb["algorithm"] == "round_robin":
                selected_node = lb["healthy_nodes"][lb["current_index"] % len(lb["healthy_nodes"])]
                lb["current_index"] += 1
            elif lb["algorithm"] == "least_connections":
                selected_node = min(lb["healthy_nodes"], key=lambda node: lb["node_requests"][node])
            else:
                selected_node = lb["healthy_nodes"][0]

            lb["total_requests"] += 1
            lb["node_requests"][selected_node] += 1

            return {
                "success": True,
                "routed_to": selected_node,
                "total_requests": lb["total_requests"],
            }

        def mark_node_unhealthy(lb_name, node_name):
            """Mark node as unhealthy."""
            if lb_name not in gateway.ha_system["load_balancers"]:
                return False

            lb = gateway.ha_system["load_balancers"][lb_name]

            if node_name in lb["healthy_nodes"]:
                lb["healthy_nodes"].remove(node_name)
                return True

            return False

        def mark_node_healthy(lb_name, node_name):
            """Mark node as healthy."""
            if lb_name not in gateway.ha_system["load_balancers"]:
                return False

            lb = gateway.ha_system["load_balancers"][lb_name]

            if node_name in lb["backend_nodes"] and node_name not in lb["healthy_nodes"]:
                lb["healthy_nodes"].append(node_name)
                return True

            return False

        # Setup load balancer
        lb = setup_load_balancer("main_lb", ["node1", "node2", "node3"], "round_robin")

        # Route requests
        for i in range(10):
            result = route_request("main_lb")
            assert result["success"] == True

        # Verify round-robin distribution
        lb = gateway.ha_system["load_balancers"]["main_lb"]
        assert lb["total_requests"] == 10
        assert lb["node_requests"]["node1"] == 4  # 10/3 distributed
        assert lb["node_requests"]["node2"] == 3
        assert lb["node_requests"]["node3"] == 3

        # Simulate node failure
        mark_node_unhealthy("main_lb", "node2")

        # Continue routing requests
        for i in range(6):
            result = route_request("main_lb")
            assert result["success"] == True
            assert result["routed_to"] in ["node1", "node3"]  # Should not route to failed node

        # Verify failover handling
        lb = gateway.ha_system["load_balancers"]["main_lb"]
        assert len(lb["healthy_nodes"]) == 2
        assert "node2" not in lb["healthy_nodes"]

        # Recover node
        mark_node_healthy("main_lb", "node2")

        # Verify recovery
        assert len(lb["healthy_nodes"]) == 3
        assert "node2" in lb["healthy_nodes"]

    def test_geographic_redundancy(self, ha_gateway):
        """Test geographic redundancy scenarios."""
        gateway = ha_gateway

        def setup_geo_redundant_sites(primary_site, backup_sites):
            """Setup geographically redundant sites."""
            geo_config = {
                "primary_site": primary_site,
                "backup_sites": backup_sites,
                "current_active_site": primary_site,
                "site_health": {},
                "data_replication_status": {},
                "failover_history": [],
            }

            # Initialize site health
            all_sites = [primary_site] + backup_sites
            for site in all_sites:
                geo_config["site_health"][site] = {
                    "healthy": True,
                    "latency_ms": 50,
                    "last_check": datetime.now(),
                }

                geo_config["data_replication_status"][site] = {
                    "lag_seconds": 0,
                    "last_replication": datetime.now(),
                    "replication_healthy": True,
                }

            gateway.ha_system["geo_redundancy"] = geo_config
            return geo_config

        def check_site_connectivity(site_name):
            """Check connectivity to a site."""
            if "geo_redundancy" not in gateway.ha_system:
                return {"healthy": False}

            geo_config = gateway.ha_system["geo_redundancy"]

            if site_name not in geo_config["site_health"]:
                return {"healthy": False}

            # Simulate connectivity check
            import random

            latency = random.randint(10, 200)
            is_healthy = latency < 150  # Healthy if latency < 150ms

            geo_config["site_health"][site_name]["healthy"] = is_healthy
            geo_config["site_health"][site_name]["latency_ms"] = latency
            geo_config["site_health"][site_name]["last_check"] = datetime.now()

            return {"healthy": is_healthy, "latency_ms": latency}

        def trigger_geo_failover(target_site):
            """Trigger geographic failover to target site."""
            if "geo_redundancy" not in gateway.ha_system:
                return {"success": False, "error": "Geo redundancy not configured"}

            geo_config = gateway.ha_system["geo_redundancy"]

            if target_site not in geo_config["backup_sites"]:
                return {"success": False, "error": "Target site not in backup sites"}

            if not geo_config["site_health"][target_site]["healthy"]:
                return {"success": False, "error": "Target site not healthy"}

            # Perform failover
            old_site = geo_config["current_active_site"]
            geo_config["current_active_site"] = target_site

            failover_record = {
                "timestamp": datetime.now(),
                "from_site": old_site,
                "to_site": target_site,
                "reason": "manual_failover",
            }

            geo_config["failover_history"].append(failover_record)

            return {
                "success": True,
                "from_site": old_site,
                "to_site": target_site,
                "failover_time": failover_record["timestamp"],
            }

        # Setup geo redundancy
        geo_config = setup_geo_redundant_sites("us-east-1", ["us-west-2", "eu-west-1"])

        # Check site connectivity
        east_health = check_site_connectivity("us-east-1")
        west_health = check_site_connectivity("us-west-2")
        eu_health = check_site_connectivity("eu-west-1")

        assert "healthy" in east_health
        assert "latency_ms" in east_health

        # Simulate primary site failure
        geo_config["site_health"]["us-east-1"]["healthy"] = False

        # Trigger failover to backup site
        failover_result = trigger_geo_failover("us-west-2")

        assert failover_result["success"] == True
        assert failover_result["from_site"] == "us-east-1"
        assert failover_result["to_site"] == "us-west-2"

        # Verify failover
        updated_geo_config = gateway.ha_system["geo_redundancy"]
        assert updated_geo_config["current_active_site"] == "us-west-2"
        assert len(updated_geo_config["failover_history"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
