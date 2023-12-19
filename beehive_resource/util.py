# SPDX-License-Identifier: EUPL-1.2
#
# (C) Copyright 2018-2023 CSI-Piemonte
from functools import wraps
from logging import getLogger

from beecell.types.type_string import str2bool
from beehive_resource.model import ResourceState

logger = getLogger(__name__)


def create_resource():
    """use this decorator with method used to create a resource."""

    def wrapper(fn):
        @wraps(fn)
        def create_resource_decorated(*args, **kwargs):
            args = list(args)
            inst = args.pop(0)
            params = args.pop(0)

            # run function
            res = fn(inst, **params)

            # finalize creation
            inst.finalize_create(**params)
            logger.debug("run method %s: %s" % (fn.__name__, res))
            return res

        return create_resource_decorated

    return wrapper


def import_resource():
    """use this decorator with method used to import a resource."""

    def wrapper(fn):
        @wraps(fn)
        def import_resource_decorated(*args, **kwargs):
            args = list(args)
            inst = args.pop(0)
            params = args.pop(0)

            # run function
            res = fn(inst, **params)

            # finalize creation
            inst.finalize_import(**params)
            logger.debug("run method %s: %s" % (fn.__name__, res))
            return res

        return import_resource_decorated

    return wrapper


def clone_resource():
    """use this decorator with method used to clone a resource."""

    def wrapper(fn):
        @wraps(fn)
        def clone_resource_decorated(*args, **kwargs):
            args = list(args)
            inst = args.pop(0)
            params = args.pop(0)

            # run function
            res = fn(inst, **params)

            # finalize creation
            inst.finalize_clone(**params)
            logger.debug("run method %s: %s" % (fn.__name__, res))
            return res

        return clone_resource_decorated

    return wrapper


def patch_resource():
    """use this decorator with method used to patch a resource."""

    def wrapper(fn):
        @wraps(fn)
        def patch_resource_decorated(*args, **kwargs):
            args = list(args)
            inst = args.pop(0)
            params = args.pop(0)

            # run function
            res = fn(inst, **params)

            # update resource
            inst.patch_internal(**params)
            inst.update_state(ResourceState.ACTIVE)

            # run an optional post update function
            inst.post_patch(**params)

            logger.debug("run method %s: %s" % (fn.__name__, res))
            return res

        return patch_resource_decorated

    return wrapper


def update_resource():
    """use this decorator with method used to update a resource."""

    def wrapper(fn):
        @wraps(fn)
        def create_update_decorated(*args, **kwargs):
            args = list(args)
            inst = args.pop(0)
            params = args.pop(0)

            # run function
            res = fn(inst, **params)

            # # update tags ans quotas
            # params = inst.update_tags(params)
            # params = inst.update_quotas(params)
            #
            # # update resource
            # params.pop('sync', None)
            # inst.update_internal(**params)

            # update state
            inst.update_state(ResourceState.ACTIVE)

            # run an optional post update function
            inst.post_update(**params)

            logger.debug("run method %s: %s" % (fn.__name__, res))
            return res

        return create_update_decorated

    return wrapper


def delete_resource():
    """use this decorator with method used to delete a resource."""

    def wrapper(fn):
        @wraps(fn)
        def create_delete_decorated(*args, **kwargs):
            args = list(args)
            inst = args.pop(0)
            params = args.pop(0)

            # run function
            res = fn(inst, **params)

            # delete resource
            inst.delete_internal()

            # run an optional post delete function
            inst.post_delete(**params)

            logger.debug("run method %s: %s" % (fn.__name__, res))
            return res

        return create_delete_decorated

    return wrapper


def expunge_resource():
    """use this decorator with method used to expunge a resource."""

    def wrapper(fn):
        @wraps(fn)
        def create_expunge_decorated(*args, **kwargs):
            args = list(args)
            inst = args.pop(0)
            params = args.pop(0)

            # run function
            res = None
            if str2bool(params.get("deep")) is True:
                res = fn(inst, **params)

            # expunge resource
            inst.expunge_internal()

            # run an optional post delete function
            inst.post_expunge(**params)

            logger.debug("run method %s: %s" % (fn.__name__, res))
            return res

        return create_expunge_decorated

    return wrapper
