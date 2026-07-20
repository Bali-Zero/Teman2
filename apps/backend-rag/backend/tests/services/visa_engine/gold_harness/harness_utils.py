"""Small shared helpers for the gold-harness test suite."""

from __future__ import annotations

from backend.services.visa_engine.compiler import CompiledProduct, CompiledRulePack


def product_by_code(pack: CompiledRulePack, product_code: str) -> CompiledProduct:
    for product in pack.products:
        if product.product_code == product_code:
            return product
    raise KeyError(f"no product {product_code!r} in compiled pack")
