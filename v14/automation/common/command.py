#!/usr/bin/python2.6
#
# Copyright 2011 Google Inc. All Rights Reserved.

__author__ = 'kbaclawski@google.com (Krystian Baclawski)'

import abc
import collections
import os.path


class Shell(object):
  """Class used to build a string representation of a shell command."""

  def __init__(self, cmd, *args, **kwargs):
    assert all(key in ['path', 'ignore_error'] for key in kwargs)

    self._cmd = cmd
    self._args = list(args)
    self._path = kwargs.get('path', '')
    self._ignore_error = bool(kwargs.get('ignore_error', False))

  def __str__(self):
    cmdline = [os.path.join(self._path, self._cmd)]
    cmdline.extend(self._args)

    cmd = ' '.join(cmdline)

    if self._ignore_error:
      cmd = '{ %s; true; }' % cmd

    return cmd

  def AddOption(self, option):
    self._args.append(option)


class Wrapper(object):
  """Wraps a command with environment which gets cleaned up after execution."""

  def __init__(self, command, cwd=None, env=None):
    # @param cwd: temporary working directory
    # @param env: dictionary of environment variables
    self._command = command
    self._prefix = Chain()
    self._suffix = Chain()

    if cwd:
      self._prefix.append(Shell('pushd', cwd))
      self._suffix.insert(0, Shell('popd'))

    if env:
      for env_var, value in env.items():
        self._prefix.append(Shell('='.join([env_var, value])))
        self._suffix.insert(0, Shell('unset', env_var))

  def __str__(self):
    return str(Chain(self._prefix, self._command, self._suffix))


class AbstractCommandContainer(collections.MutableSequence):
  """Common base for all classes that behave like command container."""

  def __init__(self, *commands):
    self._commands = list(commands)

  def __contains__(self, command):
    return command in self._commands

  def __iter__(self):
    return iter(self._commands)

  def __len__(self):
    return len(self._commands)

  def __getitem__(self, index):
    return self._commands[index]

  def __setitem__(self, index, command):
    self._commands[index] = self._ValidateCommandType(command)

  def __delitem__(self, index):
    del self._commands[index]

  def insert(self, index, command):
    self._commands.insert(index, self._ValidateCommandType(command))

  @abc.abstractmethod
  def __str__(self):
    pass

  @abc.abstractproperty
  def stored_types(self):
    pass

  def _ValidateCommandType(self, command):
    if type(command) not in self.stored_types:
      raise TypeError('Command cannot have %s type.' % type(command))
    else:
      return command

  def _StringifyCommands(self):
    cmds = []

    for cmd in self:
      if isinstance(cmd, AbstractCommandContainer) and len(cmd) > 1:
        cmds.append('{ %s; }' % cmd)
      else:
        cmds.append(str(cmd))

    return cmds


class Chain(AbstractCommandContainer):
  """Container that chains shell commands using (&&) shell operator."""

  @property
  def stored_types(self):
    return [str, Shell, Chain, Pipe]

  def __str__(self):
    return ' && '.join(self._StringifyCommands())


class Pipe(AbstractCommandContainer):
  """Container that chains shell commands using pipe (|) operator."""

  def __init__(self, *commands, **kwargs):
    assert all(key in ['input', 'output'] for key in kwargs)

    AbstractCommandContainer.__init__(self, *commands)

    self._input = kwargs.get('input', None)
    self._output = kwargs.get('output', None)

  @property
  def stored_types(self):
    return [str, Shell]

  def __str__(self):
    pipe = self._StringifyCommands()

    if self._input:
      pipe.insert(str(Shell('cat', self._input), 0))

    if self._output:
      pipe.append(str(Shell('tee', self._output)))

    return ' | '.join(pipe)


def Copy(*args, **kwargs):
  assert all(key in ['to_dir', 'recursive'] for key in kwargs.keys())

  options = []

  if 'to_dir' in kwargs:
    options.extend(['-t', kwargs['to_dir']])

  if 'recursive' in kwargs:
    options.append('-r')

  options.extend(args)

  return Shell('cp', *options)


def RemoteCopyFrom(from_machine, from_path, to_path, username=None):
  from_path = os.path.expanduser(from_path) + '/'
  to_path = os.path.expanduser(to_path) + '/'

  if username:
    login = from_machine
  else:
    login = '%s@%s' % (username, from_machine)

  return Shell('rsync', '-a', '%s:%s' % (login, from_path), to_path)


def MakeSymlink(to_path, link_name):
  return Shell('ln', '-f', '-s', '-T', to_path, link_name)


def MakeDir(*dirs):
  return Shell('mkdir', '-p', *dirs)


def RmTree(*dirs):
  return Shell('rm', '-r', '-f', *dirs)


def UnTar(tar_file, dest_dir):
  return Chain(
      MakeDir(dest_dir),
      Shell('tar', '-x', '-f', tar_file, '-C', dest_dir))
