# ovirt-imageio-daemon
# Copyright (C) 2015-2020 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

from __future__ import absolute_import

import logging
import logging.config
import os
import signal
import sys

import systemd.daemon

from . import config
from . import configloader
from . import services
from . import version

CONF_DIR = "/etc/ovirt-imageio-daemon"

log = logging.getLogger("server")
remote_service = None
local_service = None
control_service = None
running = True


def main(args):
    configure_logger()
    try:
        log.info("Starting (pid=%s, version=%s)", os.getpid(), version.string)
        configloader.load(config, [os.path.join(CONF_DIR, "daemon.conf")])
        signal.signal(signal.SIGINT, terminate)
        signal.signal(signal.SIGTERM, terminate)
        start(config)
        try:
            systemd.daemon.notify("READY=1")
            log.info("Ready for requests")
            while running:
                signal.pause()
        finally:
            stop()
        log.info("Stopped")
    except Exception:
        log.exception(
            "Service failed (remote_service=%s, local_service=%s, "
            "control_service=%s, running=%s)"
            % (remote_service, local_service, control_service, running))
        sys.exit(1)


def configure_logger():
    conf = os.path.join(CONF_DIR, "logger.conf")
    logging.config.fileConfig(conf, disable_existing_loggers=False)


def terminate(signo, frame):
    global running
    log.info("Received signal %d, shutting down", signo)
    running = False


def start(config):
    global remote_service, local_service, control_service
    assert not (remote_service or local_service or control_service)

    log.debug("Starting remote service on port %d", config.images.port)
    remote_service = services.RemoteService(config)
    remote_service.start()

    log.debug("Starting local service on socket %r", config.images.socket)
    local_service = services.LocalService(config)
    local_service.start()

    log.debug("Starting control service on socket %r", config.tickets.socket)
    control_service = services.ControlService(config)
    control_service.start()


def stop():
    global remote_service, local_service, control_service
    log.debug("Stopping services")
    remote_service.stop()
    local_service.stop()
    control_service.stop()
    remote_service = None
    local_service = None
    control_service = None
