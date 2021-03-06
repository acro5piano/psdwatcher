#!/usr/bin/env python
#coding: utf-8

import os
import sys
import time
import stat
import termcolor
import cPickle as pickle

from argparse   import ArgumentParser
from subprocess import Popen

__version__ = "1.0.1"
__author__ = "Alice1017 <https://github.com/alice1017>"

WATCH_LIST_FILE = os.environ["HOME"]+"/.psdwatcher.rc"

parser = ArgumentParser(
    prog="psdwatcher",
    version=__version__,
    description="You can watch the change log of psd file using git.")

subparsers = parser.add_subparsers(dest="subcmd")

cmd_add = subparsers.add_parser("add", help="Add PSD file at watch list.")
cmd_add.add_argument("psd_file", action="store", help="The PSD file name.")

cmd_watch = subparsers.add_parser("run", help="Start watching.")
cmd_watch.add_argument("-o", action="store", dest="log_file", help="Write out log to other file.")
cmd_watch.add_argument("--no-output-log", action="store_true", dest="not_output", help="use this option, psdwatcher don't output log.")
cmd_watch.add_argument("--dev", action="store_true", dest="dev", help="Write out development log")

cmd_list = subparsers.add_parser("list", help="Show the files that was contained watch-list")

class GitError(BaseException): pass

def git(cmd, *args, **kwargs):
    input=None

    if "input" in kwargs:
        input = kwargs["input"]
    else:
        input = ""

    proc = Popen(
        ("git", cmd) + args, stdin=-1, stdout=-1, stderr=-1)
    out, err = proc.communicate(input)

    if len(err) == 0:
        return out[:-1]
    else:
        raise GitError(err)

def is_exist_listfile():
    return os.access(WATCH_LIST_FILE, os.F_OK)

def get_watch_list():
    return pickle.load(open(WATCH_LIST_FILE))

def update_list(obj):
    pickle.dump(obj, open(WATCH_LIST_FILE,"w"))
    return

def is_in_gitrepo():
    boolean = git("rev-parse", "--is-inside-work-tree")
    if boolean == "true":
        return True
    else:
        return False

class Logger(object):

    def __init__(self, log_file=None, not_output=None):
        if log_file:
            if not os.access(log_file, os.F_OK):
                self.logfile = open(log_file, "w+")
            else:
                raise IOError("%s log file is already exist." % log_file)
        else:
            self.logfile = None

        if not_output:
            self.not_output = True
        else:
            self.not_output = False

    def log(self, string, color=None, conma=None):
        log_content = ""
        
        if color:
            log_content = termcolor.colored(string, color)
        else:
            log_content = string

        if self.logfile:
            self.logfile.write(log_content)

        if self.not_output:
            return
        
        if conma:
            print log_content,
        else:
            print log_content

        return 



def add_file(namespace):
    file_name = namespace.psd_file.split("/")[-1]
    file_ext = file_name.split(".")[-1]
    file_path = os.path.abspath(os.path.join(os.getcwd(), namespace.psd_file))
    file_dir = os.path.dirname(file_path)

    # check file can access
    if not os.access(file_path, os.F_OK):
        raise IOError("%s file does not found." % file_path)

    # check file is psd file
    if file_ext != "psd":
        raise IOError("fatal: '%s' this file is not PSD file!!" % file_name)

    # check whether there is git repository
    os.chdir(file_dir)
    if not is_in_gitrepo():
        raise IOError("fatal: Not a git repository (or any of the parent directories): .git")
    
    # get watch list
    if is_exist_listfile():
        watch_list = get_watch_list()
    else:
        watch_list = []

    # append file to watch list 
    if file_name not in [n for n,d,p in watch_list]:
        watch_list.append( (file_name, file_dir, file_path) )
        update_list(watch_list)

    else:
        raise KeyError("'%s' file is already added." % file_name)


def watch_starter(namespace):
    if is_exist_listfile():
        watch_list = get_watch_list()
    else:
        raise IOError("You doesn't add psd file to watch list yet!")

    # define the logger
    logger_opts = {
        "log_file": None,
        "not_output": None }

    if namespace.log_file:
        logger_opts["log_file"] = namespace.log_file

    if namespace.not_output:
        logger_opts["not_output"] = namespace.not_output
    
    logger = Logger(**logger_opts)
    log = logger.log

    # initialize default value
    counter = 0
    timestamp_register = {}
    binary_content = {}
    watch_list_files_length = len(watch_list)

    print "Start watching........"

    while 1:
        for file_name, file_dir, file_path in watch_list:
            try:
                if namespace.dev:
                    log("="*80)
                    log("Now watching file : %s" % termcolor.colored(file_name, "red"))
                
                # move dir
                if namespace.dev: log("Moving Directory to %s" % termcolor.colored(file_dir, "blue"))
                os.chdir(file_dir)
                
                # register original timestamp
                if counter <= watch_list_files_length:
                    if namespace.dev: log("Registring file's original timestamp: %s" % os.stat(file_path)[stat.ST_MTIME])

                    timestamp_register[file_name] = os.stat(file_path)[stat.ST_MTIME]

                    if namespace.dev: log("Registering psd file's binary content")

                    binary_content[file_name] = open(file_name).read()

                    counter += 1
                    continue

                # take a timestamp
                old_timestamp = timestamp_register[file_name]
                now_timestamp = os.stat(file_path)[stat.ST_MTIME]

                if namespace.dev:
                    log("Taking a timestamp:")
                    log("\told: %s" % timestamp_register[file_name])
                    log("\tnew: %s" % os.stat(file_path)[stat.ST_MTIME])

                # check timestamp difficult
                if old_timestamp != now_timestamp:
                    # get the binary content
                    old_bincontent = binary_content[file_name]
                    now_bincontent = open(file_name).read()

                    if namespace.dev: log("Getting the psd file's binary content")
                    
                    # check whether psd file's binary content was changed
                    if old_bincontent != now_bincontent:
                        # the file was overwritten

                        # write log
                        log("Catch the '%s' file's change!" % file_name, color="yellow")
                        log("timestamp : %s -> %s" % (old_timestamp, now_timestamp))

                        # git staging
                        log("Staging using git...", conma=True)
                        git("add", file_name)
                        log("done", "blue")

                        # git commit
                        log("Commiting using git...", conma=True)
                        commit_msg = "The '%s' file was changed. This commited by psdwatcher. Timestamp : %s -> %s" % (file_name, old_timestamp, now_timestamp)
                        git("commit", "--author", "psdwatcher <https://github.com/alice1017/psdwatcher/>",  "-m", commit_msg)
                        log("done", color="blue")

                        # update registered content
                        log("%s file's new timestamp: %s" % (termcolor.colored("Updating", "yellow"), termcolor.colored(now_timestamp, "blue")))
                        timestamp_register[file_name] = now_timestamp

                        log("%s psd file's new binary content" % termcolor.colored("Updating", "yellow"))
                        binary_content[file_name] = open(file_name).read()

                time.sleep(0.01)


            except KeyboardInterrupt:
                print "\n"
                print termcolor.colored("Caught KeyboardInterrupt!\npsdwatcher has terminated.", "yellow")
                sys.exit(0)

    
def show_watch_list(namespace):
    if is_exist_listfile():
        watch_list = get_watch_list()

        for file_name, file_dir, file_path in watch_list:
            print file_path

if __name__ == "__main__":
    if len(sys.argv) <= 1:
        parser.parse_args(["-h"])

    args = parser.parse_args()

    fn_register = {
        "add": add_file,
        "run": watch_starter,
        "list": show_watch_list}

    for key in fn_register.keys():
        if args.subcmd == key:
            fn_register[key](args)
