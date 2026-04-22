"""Organism actuators — idempotent side-effect handlers.

Each actuator subclasses ActuatorBase and exposes _execute() + _dry_run().
Usage is always through .run(params=..., correlation_id=..., dry_run=...).
"""
