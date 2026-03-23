#!/usr/bin/env python
# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2026 CSI-Piemonte


def resolve_dryrun(full_step_path: str, allow_fallback=False) -> str:
    import importlib
    module_path, class_name, method_name = full_step_path.rsplit(".", 2)

    dryrun_module_parts = module_path.split(".")
    # Insert 'dry_run' as a submodule before last part
    dryrun_module_parts.insert(-1, "dry_run")
    dryrun_module = ".".join(dryrun_module_parts)

    dryrun_class_name = class_name + "DryRun"

    try:
        mod = importlib.import_module(dryrun_module)
        cls = getattr(mod, dryrun_class_name)
        if hasattr(cls, method_name):
            return f"{dryrun_module}.{dryrun_class_name}.{method_name}"
    except (ImportError, AttributeError):
        pass

    if allow_fallback:
        # fallback to original if dry-run not found
        return full_step_path
    else:
        raise Exception("dryrun unsupported")
