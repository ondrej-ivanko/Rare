import configparser
import logging
import os
import platform
import shutil
import sys
import time
import traceback
from argparse import Namespace
from datetime import datetime
from typing import Optional

import legendary
import requests.exceptions
from PyQt5.QtCore import QThreadPool, QTimer, QT_VERSION_STR, PYQT_VERSION_STR
from PyQt5.QtWidgets import QApplication, QMessageBox
from requests import HTTPError

import rare
from rare.components.dialogs.launch_dialog import LaunchDialog
from rare.components.main_window import MainWindow
from rare.shared import (
    LegendaryCoreSingleton,
    GlobalSignalsSingleton,
    ArgumentsSingleton,
    ApiResultsSingleton,
    clear_singleton_instance
)
from rare.shared.image_manager import ImageManagerSingleton
from rare.utils import legendary_utils, config_helper
from rare.utils.paths import cache_dir, tmp_dir
from rare.widgets.rare_app import RareApp

start_time = time.strftime("%y-%m-%d--%H-%M")  # year-month-day-hour-minute
file_name = os.path.join(cache_dir, "logs", f"Rare_{start_time}.log")
if not os.path.exists(os.path.dirname(file_name)):
    os.makedirs(os.path.dirname(file_name))

logger = logging.getLogger("Rare")


def excepthook(exc_type, exc_value, exc_tb):
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print("Error")
    if exc_tb == HTTPError:
        try:
            if LegendaryCoreSingleton().login():
                return
            else:
                raise ValueError
        except Exception as e:
            logger.fatal(str(e))
            QMessageBox.warning(None, "Error", QApplication.tr("Failed to login"))
            QApplication.exit(1)
            return
    logger.fatal(tb)
    QMessageBox.warning(None, "Error", tb)
    QApplication.exit(1)


class App(RareApp):
    def __init__(self, args: Namespace):
        super(App, self).__init__()
        self.core = LegendaryCoreSingleton()
        self.args = ArgumentsSingleton(args)  # add some options

        lang = self.settings.value("language", self.core.language_code, type=str)
        self.load_translator(lang)

        # set Application name for settings
        self.mainwindow: Optional[MainWindow] = None
        self.launch_dialog: Optional[LaunchDialog] = None

        self.signals = GlobalSignalsSingleton(init=True)
        self.image_manager = ImageManagerSingleton(init=True)

        # launch app
        self.launch_dialog = LaunchDialog(parent=None)
        self.launch_dialog.quit_app.connect(self.launch_dialog.close)
        self.launch_dialog.quit_app.connect(lambda ec: exit(ec))
        self.launch_dialog.start_app.connect(self.start_app)
        self.launch_dialog.start_app.connect(self.launch_dialog.close)

        self.launch_dialog.login()

        dt_exp = datetime.fromisoformat(self.core.lgd.userdata['expires_at'][:-1])
        dt_now = datetime.utcnow()
        td = abs(dt_exp - dt_now)
        self.timer = QTimer()
        self.timer.timeout.connect(self.re_login)
        self.timer.start(int(td.total_seconds() - 60) * 1000)

    def re_login(self):
        logger.info("Session expires shortly. Renew session")
        try:
            self.core.login()
        except requests.exceptions.ConnectionError:
            self.timer.start(3000)  # try again if no connection
            return
        dt_exp = datetime.fromisoformat(self.core.lgd.userdata['expires_at'][:-1])
        dt_now = datetime.utcnow()
        td = abs(dt_exp - dt_now)
        self.timer.start(int(td.total_seconds() - 60) * 1000)

    def start_app(self):
        for igame in self.core.get_installed_list():
            if not os.path.exists(igame.install_path):
                # lk; since install_path is lost anyway, set keep_files to True
                # lk: to avoid spamming the log with "file not found" errors
                legendary_utils.uninstall_game(self.core, igame.app_name, keep_files=True)
                logger.info(f"Uninstalled {igame.title}, because no game files exist")
                continue
            # lk: games that don't have an override and can't find their executable due to case sensitivity
            # lk: will still erroneously require verification. This might need to be removed completely
            # lk: or be decoupled from the verification requirement
            if override_exe := self.core.lgd.config.get(igame.app_name, "override_exe", fallback=""):
                igame_executable = override_exe
            else:
                igame_executable = igame.executable
            if not os.path.exists(os.path.join(igame.install_path, igame_executable.replace("\\", "/").lstrip("/"))):
                igame.needs_verification = True
                self.core.lgd.set_installed_game(igame.app_name, igame)
                logger.info(f"{igame.title} needs verification")

        self.mainwindow = MainWindow()
        self.mainwindow.exit_app.connect(self.exit_app)

        if not self.args.silent:
            self.mainwindow.show()

        if self.args.test_start:
            self.exit_app(0)

    def exit_app(self, exit_code=0):
        threadpool = QThreadPool.globalInstance()
        threadpool.waitForDone()
        if self.timer is not None:
            self.timer.stop()
            self.timer.deleteLater()
            self.timer = None
        if self.mainwindow is not None:
            self.mainwindow.close()
            self.mainwindow = None
        clear_singleton_instance(self.signals)
        clear_singleton_instance(self.args)
        clear_singleton_instance(ApiResultsSingleton())
        self.processEvents()
        shutil.rmtree(tmp_dir)
        os.makedirs(tmp_dir)

        self.exit(exit_code)


def start(args):
    # set excepthook to show dialog with exception
    sys.excepthook = excepthook

    # configure logging
    if args.debug:
        logging.basicConfig(
            format="[%(name)s] %(levelname)s: %(message)s", level=logging.DEBUG
        )
        logging.getLogger().setLevel(level=logging.DEBUG)
        # keep requests, asyncio and pillow quiet
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)
        logger.info(
            f"Launching Rare version {rare.__version__} Codename: {rare.code_name}\n"
            f" - Using Legendary {legendary.__version__} Codename: {legendary.__codename__} as backend\n"
            f" - Operating System: {platform.system()}, Python version: {platform.python_version()}\n"
            f" - Running {sys.executable} {' '.join(sys.argv)}\n"
            f" - Qt version: {QT_VERSION_STR}, PyQt version: {PYQT_VERSION_STR}"
        )
    else:
        logging.basicConfig(
            format="[%(name)s] %(levelname)s: %(message)s",
            level=logging.INFO,
            filename=file_name,
        )
        logger.info(f"Launching Rare version {rare.__version__}")
        logger.info(f"Operating System: {platform.system()}")

    while True:
        core = LegendaryCoreSingleton(init=True)
        config_helper.init_config_handler(core)
        app = App(args)
        exit_code = app.exec_()
        # if not restart
        # restart app
        del app
        core.exit()
        clear_singleton_instance(core)
        if exit_code != -133742:
            break


