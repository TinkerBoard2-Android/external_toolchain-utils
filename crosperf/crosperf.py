#!/usr/bin/python2

# Copyright 2011 Google Inc. All Rights Reserved.
"""The driver script for running performance benchmarks on ChromeOS."""

from __future__ import print_function

import atexit
import optparse
import os
import signal
import sys
from experiment_runner import ExperimentRunner
from experiment_runner import MockExperimentRunner
from experiment_factory import ExperimentFactory
from experiment_file import ExperimentFile
from help import Help
from settings_factory import GlobalSettings
from utils import logger

import test_flag


class MyIndentedHelpFormatter(optparse.IndentedHelpFormatter):

  def format_description(self, description):
    return description


def SetupParserOptions(parser):
  """Add all options to the parser."""
  parser.add_option('--dry_run',
                    dest='dry_run',
                    help=('Parse the experiment file and '
                          'show what will be done'),
                    action='store_true',
                    default=False)
  # Allow each of the global fields to be overridden by passing in
  # options. Add each global field as an option.
  option_settings = GlobalSettings('')
  for field_name in option_settings.fields:
    field = option_settings.fields[field_name]
    parser.add_option('--%s' % field.name,
                      dest=field.name,
                      help=field.description,
                      action='store')


def ConvertOptionsToSettings(options):
  """Convert options passed in into global settings."""
  option_settings = GlobalSettings('option_settings')
  for option_name in options.__dict__:
    if (options.__dict__[option_name] is not None and
        option_name in option_settings.fields):
      option_settings.SetField(option_name, options.__dict__[option_name])
  return option_settings


def Cleanup(experiment):
  """Handler function which is registered to the atexit handler."""
  experiment.Cleanup()


def CallExitHandler(signum, _):
  """Signal handler that transforms a signal into a call to exit.

  This is useful because functionality registered by "atexit" will
  be called. It also means you can "catch" the signal by catching
  the SystemExit exception.
  """
  sys.exit(128 + signum)


def Main(argv):
  parser = optparse.OptionParser(usage=Help().GetUsage(),
                                 description=Help().GetHelp(),
                                 formatter=MyIndentedHelpFormatter(),
                                 version='%prog 3.0')

  parser.add_option('--noschedv2',
                    dest='noschedv2',
                    default=False,
                    action='store_true',
                    help=('Do not use new scheduler. '
                          'Use original scheduler instead.'))
  parser.add_option('-l',
                    '--log_dir',
                    dest='log_dir',
                    default='',
                    help='The log_dir, default is under <crosperf_logs>/logs')

  SetupParserOptions(parser)
  options, args = parser.parse_args(argv)

  # Convert the relevant options that are passed in into a settings
  # object which will override settings in the experiment file.
  option_settings = ConvertOptionsToSettings(options)
  log_dir = os.path.abspath(os.path.expanduser(options.log_dir))
  logger.GetLogger(log_dir)

  if len(args) == 2:
    experiment_filename = args[1]
  else:
    parser.error('Invalid number arguments.')

  working_directory = os.getcwd()
  if options.dry_run:
    test_flag.SetTestMode(True)

  experiment_file = ExperimentFile(
      open(experiment_filename, 'rb'), option_settings)
  if not experiment_file.GetGlobalSettings().GetField('name'):
    experiment_name = os.path.basename(experiment_filename)
    experiment_file.GetGlobalSettings().SetField('name', experiment_name)
  experiment = ExperimentFactory().GetExperiment(experiment_file,
                                                 working_directory, log_dir)

  json_report = experiment_file.GetGlobalSettings().GetField('json_report')

  signal.signal(signal.SIGTERM, CallExitHandler)
  atexit.register(Cleanup, experiment)

  if options.dry_run:
    runner = MockExperimentRunner(experiment, json_report)
  else:
    runner = ExperimentRunner(experiment,
                              json_report,
                              using_schedv2=(not options.noschedv2))

  runner.Run()


if __name__ == '__main__':
  Main(sys.argv)
