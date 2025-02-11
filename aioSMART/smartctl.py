# Copyright (C) 2021 Rafael Leira, Naudit HPCN S.L.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License,
# version 2, as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA  02110-1301, USA.
#
################################################################
from asyncio.subprocess import PIPE
import asyncio
from .utils import SMARTCTL_PATH, any_in
from typing import List, Tuple, Union, Optional

import logging
import os
try:
    import ujson as json
except ImportError:
    import json

logger = logging.getLogger('aioSMART')

os.environ["LANG"] = "C"


class Smartctl:
    def __init__(self, smartctl_path=SMARTCTL_PATH, options: List[str] = [], sudo: Union[bool, List[str]] = False):
        """
        Instantiates and initializes the Smartctl wrapper.

        Args:
            smartctl_path (str | PathLike): path to the smartctl executable
            options (List[str]): extra options to use when invoking smartctl
            sudo (bool | List[str]):
                if True use sudo -E when calling smartctl on POSIX systems.
                If given as a list, then these arguments are passed to sudo.
                (e.g. `sudo=['-u', 'foo']` will run `sudo -u foo ...`).
        """
        self.smartctl_path = smartctl_path
        self.options: List[str] = options
        self._sudo: Union[None, List[str]] = None
        self.sudo = sudo

    @property
    def sudo(self):
        """
        Example:
            >>> # xdoctest: +REQUIRES(POSIX)
            >>> self = Smartctl()
            >>> print(f'self.sudo={self.sudo}')
            >>> self.sudo = True
            >>> print(f'self.sudo={self.sudo}')
            >>> self.sudo = []
            >>> print(f'self.sudo={self.sudo}')
            >>> self.sudo = False
            >>> print(f'self.sudo={self.sudo}')
            self.sudo=None
            self.sudo=['-E']
            self.sudo=[]
            self.sudo=None
        """
        return self._sudo

    @sudo.setter
    def sudo(self, value):
        if not isinstance(value, list):
            if value:
                # Setting sudo=True corresponds to ['-E'] by default
                value = ['-E']
            else:
                # Falsy non-list values become None
                value = None

        if value is not None and os.name != 'posix':
            logger.warn('Setting sudo is ignored on non-posix systems')
        self._sudo = value

    def add_options(self, new_options: List[str]):
        """Adds options to be passed on some smartctl queries

        Args:
            new_options (List[str]): A list of options in raw smartctl format
        """
        self.options = self.options + new_options

    async def generic_call(self, params: List[str], pass_options=False) -> Tuple[dict, int]:
        """Generic smartctl query

        Args:
            params (List[str]): The list of arguments to be passed
            pass_options (bool, optional): If true options list would be passed. Defaults to False.

        Returns:
            Tuple[List[str], int]: A raw line-by-line output from smartctl and the process return code
        """
        if not self.smartctl_path:
            raise FileNotFoundError("Command smartctl doesn't exist!")

        popen_list = []
        if os.name == 'posix':
            if self.sudo is not None:
                popen_list.extend(['sudo'] + self.sudo)

        popen_list.append(self.smartctl_path)

        if pass_options:
            popen_list.extend(self.options)

        popen_list.extend(params)

        logger.trace("Executing the following cmd: {0}".format(popen_list))

        return await self._exec(popen_list)

    async def try_generic_call(self, params: List[str], pass_options=False) -> Tuple[dict, int]:
        """Generic smartctl query
           However, if the command fails or crashes, it will return an empty list and a return code of 1 instead of raising an exception

        Args:
            params (List[str]): The list of arguments to be passed
            pass_options (bool, optional): If true options list would be passed. Defaults to False.

        Returns:
            Tuple[List[str], int]: A raw line-by-line output from smartctl and the process return code
        """

        try:
            return await self.generic_call(params, pass_options)
        except Exception as e:
            logger.debug(f"Exception while executing smartctl: {e}")
            return {}, 1

    async def _exec(self, cmd: List[str]) -> Tuple[dict, int]:
        """Executes a command and returns the output and the return code

        Args:
            cmd (List[str]): The command to be executed

        Returns:
            Tuple[List[str], int]: A raw line-by-line output from smartctl and the process return code
        """
        if not any_in(cmd, "-j", "--json"):
            cmd.append("-j")  # use json to parse
        proc = await asyncio.create_subprocess_exec(cmd[0], *cmd[1:], stdout=PIPE, stderr=PIPE)

        _stdout, _stderr = [i.decode('utf8') for i in await proc.communicate()]

        return json.loads(_stdout), proc.returncode

    async def scan(self) -> dict:
        """Queries smartctl with option --scan-open

        Returns:
            List[str]: A raw line-by-line output from smartctl
        """
        return (await self.generic_call(['--scan-open']))[0]

    async def health(self, disk: str, interface: Optional[str] = None) -> dict:
        """Queries smartctl with option --health

        Args:
            disk (str): the disk os-full-path
            interface (str, optional): the disk interface (ata,scsi,nvme,...). Defaults to None.

        Returns:
            List[str]: A raw line-by-line output from smartctl
        """
        if interface:
            return (await self.generic_call(['-d', interface, '--health', disk]))[0]
        else:
            return (await self.generic_call(['--health', disk]))[0]

    async def info(self, disk: str, interface: Optional[str] = None) -> dict:
        """Queries smartctl with option --info

        Args:
            disk (str): the disk os-full-path
            interface (str, optional): the disk interface (ata,scsi,nvme,...). Defaults to None.

        Returns:
            List[str]: A raw line-by-line output from smartctl
        """

        if interface:
            return await (self.generic_call(['-d', interface, '--info', disk], pass_options=True))[0]
        else:
            return await (self.generic_call(['--info', disk], pass_options=True))[0]

    async def all(self, disk: str, interface: Optional[str] = None) -> dict:
        """Queries smartctl with option --all

        Args:
            disk (str): the disk os-full-path
            interface (str, optional): the disk interface (ata,scsi,nvme,...). Defaults to None.

        Returns:
            List[str]: A raw line-by-line output from smartctl
        """

        if interface:
            return (await self.generic_call(['-d', interface, '--all', disk], pass_options=True))[0]
        else:
            return (await self.generic_call(['--all', disk], pass_options=True))[0]

    async def test_stop(self, disk_type: str, disk: str) -> int:
        """Queries smartctl with option -X

        Args:
            disk_type (str): the disk type
            disk (str): the disk os-full-path

        Returns:
            int: the smartctl process return code
        """
        return (await self.generic_call(['-d', disk_type, '-X', disk]))[1]

    async def test_start(self, disk_type: str, test_type: str, disk: str) -> Tuple[dict, int]:
        """Queries smartctl with option -t <test_type>

        Args:
            disk_type (str): the disk type
            test_type (str): the test type
            disk (str): the disk os-full-path

        Returns:
            Tuple[List[str], int]: A raw line-by-line output from smartctl and the process return code
        """
        return await self.generic_call(['-d', disk_type, '-t', test_type, disk])


# A global smartctl object used as the defaults in Device and DeviceList.
SMARTCTL = Smartctl()
