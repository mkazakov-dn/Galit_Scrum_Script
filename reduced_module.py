#!/usr/bin/env python3
from __future__ import annotations

import re
from enum import Enum
from typing import List, Optional, Union
from datetime import datetime

# netmiko imports
from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException
from netmiko.exceptions import NetmikoTimeoutException
from netmiko.exceptions import NetmikoBaseException
from netmiko.exceptions import ReadException, ReadTimeout, WriteException

class SSH_Conn:
    class SSH_ENUMS:
        class EXEC_MODE(Enum):
            SHOW = 1
            CFG = 2
            SHELL = 3
            HOST = 3
            NETNS = 3
            GDB = 4

        class CLI_MODE(str, Enum):
            cli_id: int
            category: str

            def __new__(cls, cli_id: int, category: str):
                obj = str.__new__(cls, cli_id)
                obj._value_ = cli_id
                obj.category = category
                return obj

            NOT_CONNECTED = 'NOT_CONNECTED', 'CLOSED'
            DNOS_SHOW = 'DNOS_SHOW', 'DNOS'
            DNOS_CFG = 'DNOS_CFG', 'DNOS'
            SHELL = 'SHELL', 'SHELL'
            HOST = 'HOST', 'SHELL'
            NETNS = 'NETNS', 'SHELL'
            RESCUE = 'RESCUE', 'DEBUG'
            GDB = 'GDB', 'DEBUG'

    class __private_exec_output:
        def __init__(self, return_obj_type: type = str):
            self._exec_output = {}
            if return_obj_type is str or return_obj_type is list or return_obj_type is dict:
                self._return_obj_type = return_obj_type
            else:
                self.return_obj_type = str
            self._exec_index = 0

        def add_entry(self, cmd: str = None, single_output: str = None):
            if cmd is not None and single_output is not None:
                if isinstance(cmd, str) and isinstance(single_output, str):
                    my_tuple = [cmd, single_output]
                    self._exec_output[self._exec_index] = my_tuple
                    self._exec_index += 1

        def get_output_object(self):
            output = None
            if self._return_obj_type is str:
                output = self.__get_output_as_string()
                if output is None:
                    output = ''
            elif self._return_obj_type is list:
                output = self.__get_output_as_list()
                if output is None:
                    output = []
            elif self._return_obj_type is dict:
                output = self.__get_output_as_dict()
                if output is None:
                    output = {}
            return output

        def __get_output_as_string(self):
            output_as_string = ''
            if len(self._exec_output) > 0:
                for i in range(self._exec_index):
                    output_as_string += self._exec_output[i][1] + '\n'
                return output_as_string
            else:
                return None

        def __get_output_as_list(self):
            output_as_list = []
            if len(self._exec_output) > 0:
                for i in range(self._exec_index):
                    output_as_list.append(self._exec_output[i][1])
                return output_as_list
            else:
                return None

        def __get_output_as_dict(self):
            output_as_dict = {}
            if len(self._exec_output) > 0:
                for i in range(self._exec_index):
                    key = self._exec_output[i][0]
                    value = self._exec_output[i][1]
                    if key in output_as_dict.keys():
                        output_as_dict[key].append(value)
                    else:
                        value = [value]
                        output_as_dict[key] = value
                return output_as_dict
            else:
                return None

    def __init__(self, host,
                 authentication: ssh_auth | list = None,
                 change_mode_retry: int = 3,
                 session_log: str = 'filename',
                 localized_exec: bool = True,
                 reconnect: bool = True,
                 reconnect_retry: int = 3,
                 mitigate_retry: int = 3,
                 icmp_test: bool = True,
                 icmp_fast: bool = True,
                 icmp_vars: list | dict = None,
                 cfg_commit_on_exit: bool = False,
                 output_obj_type: type = str):

        self.__host = host
        self.__session_log = session_log
        self.__localized_exec = localized_exec
        self.__return_obj_type = output_obj_type if output_obj_type in [str, list, dict] else str
        self._isOpen = False
        self._net_connect: ConnectHandler = None
        self._cli_lvl = self.SSH_ENUMS.CLI_MODE.NOT_CONNECTED
        self._cli_expect_prompt = r'#'
        self._hostname = None

    def connect(self, task_id: int = 0):
        try:
            if self._net_connect is None:
                if self.__session_log == 'filename':
                    self._net_connect = ConnectHandler(
                        device_type="linux",
                        host=self.__host,
                        username='dnroot',
                        password='dnroot',
                        banner_timeout=120,
                        conn_timeout=120,
                        auth_timeout=120,
                        blocking_timeout=120,
                        read_timeout_override=60,
                        global_delay_factor=0.10,
                        fast_cli=True,
                        auto_connect=True
                    )
                else:
                    self._net_connect = ConnectHandler(
                        device_type="linux",
                        host=self.__host,
                        username='dnroot',
                        password='dnroot',
                        session_log=self.__session_log,
                        banner_timeout=120,
                        conn_timeout=120,
                        auth_timeout=120,
                        blocking_timeout=120,
                        read_timeout_override=60,
                        global_delay_factor=0.10,
                        fast_cli=True,
                        auto_connect=True
                    )
                self._isOpen = True
                self._cli_lvl = self.SSH_ENUMS.CLI_MODE.DNOS_SHOW

        except NetmikoAuthenticationException as error:
            raise Exception("ERROR: SSH authentication failed!")

        except NetmikoTimeoutException:
            if self.__reconnect:
                task_id += 1
                if self.__reconnect_retry > task_id:
                    self.connect(task_id=task_id)
                else:
                    raise Exception(f"ERROR: Timeout in connection to Node - {self.__host}, tried {str(task_id)} times")
            else:
                raise Exception(f"ERROR: Timeout in connection to Node - {self.__host}")

    def disconnect(self):
        if self._isOpen:
            try:
                self._net_connect.sock.close()
                self._isOpen = False
            except:
                self._isOpen = False
                pass

    def exec_command(self, cmd, exec_mode: SSH_ENUMS.EXEC_MODE = None, netns: str = None,
                     timeout: int = 10, one_screen_only: bool = False,
                     output_object_type: type = None, location_target: dict = None,
                     interactive: SSH_ENUMS.INTERACTIVE_RESPONSE = None, interactive_pass: str = None):
        if self._isOpen:
            if exec_mode is None or not isinstance(exec_mode, self.SSH_ENUMS.EXEC_MODE):
                exec_mode = self.SSH_ENUMS.EXEC_MODE.SHOW

            _exec_output = ''
            if exec_mode is self.SSH_ENUMS.EXEC_MODE.SHOW:
                if one_screen_only is False:
                    tmp_exp_cli = re.escape(self._cli_expect_prompt)
                    _exec_output = self.__exec_single_or_bulk(cmd_list=cmd, timeout=timeout, exp_prompt=tmp_exp_cli,
                                                              verify=False, interactive=interactive,
                                                              interactive_pass=interactive_pass,
                                                              output_object_type=output_object_type,
                                                              check_no_more=True)
                else:
                    tmp_exp_cli = re.escape(self._cli_expect_prompt)
                    _exec_output = self.__exec_single_or_bulk(cmd_list=cmd, timeout=timeout, exp_prompt=tmp_exp_cli,
                                                              interactive_pass=interactive_pass,
                                                              verify=False, interactive=interactive,
                                                              output_object_type=output_object_type)
            elif exec_mode is self.SSH_ENUMS.EXEC_MODE.CFG:
                if self._cli_lvl is self.SSH_ENUMS.CLI_MODE.DNOS_CFG:
                    tmp_exp_cli = re.escape(self._hostname + "(cfg)" + self._cli_expect_prompt)
                    _exec_output = self.__exec_single_or_bulk(cmd_list=cmd, timeout=timeout, exp_prompt=tmp_exp_cli,
                                                              verify=False, interactive=interactive,
                                                              interactive_pass=interactive_pass,
                                                              output_object_type=output_object_type)

            return _exec_output

    def __exec_single_or_bulk(self, cmd_list, timeout, exp_prompt, verify: bool = True,
                              interactive: SSH_ENUMS.INTERACTIVE_RESPONSE = None, output_object_type: type = None,
                              check_no_more: bool = False, interactive_pass=None):
        if output_object_type is not None:
            _exec_output = self.__private_exec_output(return_obj_type=output_object_type)
        else:
            _exec_output = self.__private_exec_output(return_obj_type=self.__return_obj_type)

        if isinstance(cmd_list, list):
            for i in cmd_list:
                if check_no_more:
                    if re.search(r"\|\sno-more", i) is None:
                        i = f"{i} | no-more"
                _single_output = self.__exec_single_cmd(cmd=i, timeout=timeout, exp_prompt=exp_prompt,
                                                        verify=verify, output_obj=_exec_output)
        elif isinstance(cmd_list, str):
            if check_no_more:
                if re.search(r"\|\sno-more", cmd_list) is None:
                    cmd_list = f"{cmd_list} | no-more"
            _single_output = self.__exec_single_cmd(cmd=cmd_list, timeout=timeout, exp_prompt=exp_prompt,
                                                    verify=verify, output_obj=_exec_output)

        return _exec_output.get_output_object()

    def __exec_single_cmd(self, cmd: str, timeout, exp_prompt: str, verify: bool = True,
                          output_obj: __private_exec_output = None):
        if output_obj is None:
            output_obj = self.__private_exec_output(return_obj_type=self.__return_obj_type)

        if cmd is None or not isinstance(cmd, str):
            return ''

        if exp_prompt is None or not isinstance(cmd, str):
            return ''

        if verify:
            _exec_output = self._net_connect.send_command(cmd, expect_string=exp_prompt,
                                                          read_timeout=timeout)
        else:
            _exec_output = self._net_connect.send_command(cmd, expect_string=exp_prompt,
                                                          read_timeout=timeout,
                                                          cmd_verify=False)

        if _exec_output is not None:
            _exec_output = self.__int_strip_ansi(_exec_output)
            if _exec_output.rfind('\n') != -1:
                last_line = _exec_output.splitlines()[-1]
                last_line = '\n'
                _exec_output = _exec_output[:_exec_output.rfind('\n')] + last_line

        output_obj.add_entry(cmd=cmd, single_output=_exec_output)

    def __int_strip_ansi(self, line):
        pattern = re.compile(r'\x1B\[\d+(;\d+){0,2}m')
        stripped = pattern.sub('', line)
        pattern = re.compile(r'\x1B\[F')
        stripped = pattern.sub('', stripped)
        pattern = re.compile(r'^.*\x07')
        stripped = pattern.sub('', stripped)
        return stripped

    def get_hostname(self):
        if self._isOpen:
            if self._cli_lvl is self.SSH_ENUMS.CLI_MODE.DNOS_SHOW or self._cli_lvl is self.SSH_ENUMS.CLI_MODE.DNOS_CFG:
                self._hostname = re.match(r"(.*)#",
                                          self.__int_strip_ansi(self._net_connect.find_prompt())).groups()[0]
                # remove potential date-time logging added (anything in brackets will be removed)
                self._hostname = re.sub(r"\(.*\)", "", self._hostname)
                # remove linux command preamble code
                self._hostname = re.sub(r"\\x1b\[F", "", self._hostname)
            return self._hostname

    def commit_cfg(self, commit_name: str = "auto_datetime", timeout: int = 30, commit_check: bool = True):
        # If commit name is default, generate name with datetime
        if commit_name == "auto_datetime":
            commit_name = "auto_" + datetime.now().strftime("%m/%d/%YT%H_%M_%S")

        # Check if connection is open
        if self._isOpen and self._cli_lvl is self.SSH_ENUMS.CLI_MODE.DNOS_CFG:
            # can try to commit the cfg
            commit_done = True
            tmp_prompt = self._hostname + "\(cfg\)" + self._cli_expect_prompt
            
            # we should run commit check, we wait for 30sec for potential large commit
            if commit_check is True:
                __output = self._net_connect.send_command("commit check",
                                                          expect_string=tmp_prompt,
                                                          cmd_verify=False,
                                                          read_timeout=timeout)
            else:
                __output = 'ok'
                
            # is commit needed?
            if not re.search("NOTICE: commit action is not applicable", __output):
                # we have commit, check if no error was seen in the validation
                if not re.search("ERROR:", __output):
                    # we have no error commit can be made
                    # try to commit, it should not fail -> try/except just in case of commit timeout
                    tmp_prompt = 'Commit succeeded'
                    try:
                        __output = self._net_connect.send_command("commit log " + commit_name,
                                                                  cmd_verify=False,
                                                                  read_timeout=timeout)
                    except:
                        commit_done = False
                else:
                    # we can't commit so return False as commit not performed
                    commit_done = False

            # we are done, return output
            return commit_done

    def change_mode(self, requested_cli: SSH_ENUMS.CLI_MODE = None, node: str = 'ncc',
                    node_id: str = 'active', container: str = '', netns: str = '',
                    shell_password: str = None, host_password: str = None):
        # Check if connection is open
        if not self._isOpen:
            return False

        # If no specific mode requested, just return current mode
        if requested_cli is None:
            return True

        # Check if we're already in the requested mode
        if self._cli_lvl is requested_cli:
            return True

        # Handle mode changes
        if self._cli_lvl is self.SSH_ENUMS.CLI_MODE.DNOS_SHOW:
            if requested_cli is self.SSH_ENUMS.CLI_MODE.DNOS_CFG:
                return self.__enter_cfg_mode()
        elif self._cli_lvl is self.SSH_ENUMS.CLI_MODE.DNOS_CFG:
            if requested_cli is self.SSH_ENUMS.CLI_MODE.DNOS_SHOW:
                return self.__exit_cfg_mode()

        return False

    def __enter_cfg_mode(self):
        # Check if connection is open
        if self._isOpen and self._cli_lvl is self.SSH_ENUMS.CLI_MODE.DNOS_SHOW:
            # Get hostname before entering config mode
            self._hostname = re.match(r"(.*)#",
                                    self.__int_strip_ansi(self._net_connect.find_prompt())).groups()[0]
            # remove potential date-time logging added (anything in brackets will be removed)
            self._hostname = re.sub(r"\(.*\)", "", self._hostname)
            # remove linux command preamble code
            self._hostname = re.sub(r"\\x1b\[F", "", self._hostname)
            
            # can try to enter cfg mode
            # enter config mode
            output = self._net_connect.send_command("configure",
                                                    cmd_verify=False,
                                                    expect_string=self._cli_expect_prompt)
            # change cfg mode value
            self._cli_lvl = self.SSH_ENUMS.CLI_MODE.DNOS_CFG

            if output is not None:
                return True
            else:
                return False

    def __exit_cfg_mode(self):
        # Check if connection is open
        if self._isOpen and self._cli_lvl is self.SSH_ENUMS.CLI_MODE.DNOS_CFG:
            # Just exit config mode without checking for changes
            output = self._net_connect.send_command("end", cmd_verify=False,
                                                    expect_string=(self._hostname + self._cli_expect_prompt))
            if output is not None:
                # change cli_lvl to read_mode
                self._cli_lvl = self.SSH_ENUMS.CLI_MODE.DNOS_SHOW
                return True
            else:
                return False
        else:
            return False 