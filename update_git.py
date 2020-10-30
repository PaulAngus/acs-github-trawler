#!/usr/bin/env python

# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""
Usage:
  fixed_issues.py [--config=<config.json>]
                  [-t <arg> | --gh_token=<arg>] 
                  [-c <arg> | --prev_rel_commit=<arg>]
                  [-b <arg> | --branch=<arg>]  
                  [--repo=<arg>] 
                  [--gh_base_url=<arg>] 
                  [--col_title_width=<arg>] 

  fixed_issues.py (-h | --help)
Options:
  -h --help                         Show this screen.
  --config=<config.json>            Path to a JSON config file with an object of config options.
  --gh_token=<arg>         Required: Your Github token from https://github.com/settings/tokens 
                                      with `repo/public_repo` permissions.
  --prev_rel_commit=<arg>  Required: The commit hash of the previous release.
  --branches=<arg>         Required: Comma separated list of branches to report on (eg: 4.7,4.8,4.9).
  --new_release_ver=<arg            not used in this iteration yet

                                      The last one is assumed to be `master`, so `4.7,4.8,4.9` would
                                      actually be represented by 4.7, 4.8 and master.
  --repo=<arg>                      The name of the repo to use [default: apache/cloudstack].
  --gh_base_url=<arg>               The base Github URL for pull requests 
                                      [default: https://github.com/apache/cloudstack/pull/].
  --col_title_width=<arg>          The width of the title column [default: 60].
  --docker_created_config=<arg>     used to know whether to remove conf file if in container (for some safety)    

Sample json file contents:

{
	"--gh_token":"******************",
	"--prev_release_commit":"",
	"--repo_name":"apache/cloudstack",
	"--branch":"4.11",
	"--prev_release_ver":"4.11.1.0",
	"--new_release_ver":"4.11.2.0"
}

requires: python3.8 + docopt pygithub prettytable gitpython

"""

from typing import DefaultDict
import docopt
import json
from github import Github
from prettytable import PrettyTable
import os.path
from os import path
import re
import sys
import subprocess
from datetime import datetime
import subprocess
import pygit2
import shutil

def load_config():
    """
    Parse the command line arguments and load in the optional config file values
    """
    args = docopt.docopt(__doc__)
    if args['--config'] and os.path.isfile(args['--config']):
        json_args = {}
        try:
            with open(args['--config']) as json_file:    
                json_args = json.load(json_file)
        except Exception as e:
            print(("Failed to load config file '%s'" % args['--config']))
            print(("ERROR: %s" % str(e)))
        if json_args:
            args = merge(args, json_args)
    #     since we are here, check that the required fields exist
    valid_input = True
    for arg in ['--gh_token', '--prev_release_ver', '--branch', '--repo', '--new_release_ver']:
        if not args[arg] or (isinstance(args[arg], list) and not args[arg][0]):
            print(("ERROR: %s is required" % arg))
            valid_input = False
    if not valid_input:
        sys.exit(__doc__)
    return args

leading_4_spaces = re.compile('^    ')

def merge(primary, secondary):
    """
    Merge two dictionaries.
    Values that evaluate to true take priority over false values.
    `primary` takes priority over `secondary`.
    """
    return dict((str(key), primary.get(key) or secondary.get(key))
                for key in set(secondary) | set(primary))


def get_commits():
    print("- Cloning repo, sorry, this could take a while")
    dir_now = os.getcwd()
    if path.isdir(cloned_repo_dir):
        shutil.rmtree(cloned_repo_dir)
    os.mkdir(cloned_repo_dir)
    os.chdir(cloned_repo_dir)
    repoClone = pygit2.clone_repository(repo.git_url, cloned_repo_dir, bare=True, checkout_branch=branch)
    lines = subprocess.check_output(
        ['git', 'log'], stderr=subprocess.STDOUT
            ).decode("utf-8").split("\n")
    commits = []
    current_commit = {}
    def save_current_commit():
        title = current_commit['message'][0]
        message = current_commit['message'][1:]
        if message and message[0] == '':
            del message[0]
        current_commit['title'] = title
        current_commit['message'] = '\n'.join(message)
        commits.append(current_commit)
    for line in lines:
        if not line.startswith(' '):
            if line.startswith('commit '):
                if current_commit:
                    save_current_commit()
                    current_commit = {}
                current_commit['hash'] = line.split('commit ')[1]
            else:
                try:
                    key, value = line.split(':', 1)
                    current_commit[key.lower()] = value.strip()
                except ValueError:
                    pass
        else:
            current_commit.setdefault(
                'message', []
            ).append(leading_4_spaces.sub('', line))
    if current_commit:
        save_current_commit()
    os.chdir(dir_now)
    return commits

# run the code...
if __name__ == '__main__':
    print('\nInitialising...\n\n')

    args = load_config()
#   repository details
    gh_token = args['--gh_token']
    gh = Github(gh_token)
    repo_name = args['--repo']
    prev_release_ver = args['--prev_release_ver']
    prev_release_commit = args['--prev_release_commit']
    new_release_ver = args['--new_release_ver']
    branch = args['--branch']
    
    gh_base_url = args['--gh_base_url']

    # default column width to 60
    if 'col_title_width' in locals():
        col_title_width = int(args['--col_title_width'])
    else:
        col_title_width = 60
    
    prs_file = "prs.rst"
    cloned_repo_dir = '/tmp/repo'
    wip_features_table = PrettyTable(["PR Number", "Title", "Priority", "blank"])
    fixes_table = PrettyTable(["PR Number", "Title", "Priority", "blank"]) 
    features_table = PrettyTable(["PR Number", "Title", "Priority", "blank"])
    dontknow_table = PrettyTable(["PR Number", "Title", "Priority", "blank"])
    wip_features_table.align["Title"] = "l"
    features_table.align["Title"] = "l"
    fixes_table.align["Title"] = "l"
    dontknow_table.align["Title"] = "l"
    wip_features_table._max_width = {"Title":col_title_width}
    features_table._max_width = {"Title":col_title_width}
    fixes_table._max_width = {"Title":col_title_width}
    dontknow_table._max_width = {"Title":col_title_width}
    
    repo = gh.get_repo(repo_name)

    ## TODO - get commit -> commit date from tag on master.
    ## Searching seems a waste

    #repo_tags = repo.get_tags()

    if prev_release_commit:
        print("Previous Release Commit SHA found in conf file, skipping pre release SHA search.\n")
        prev_release_sha = prev_release_commit
    else:
        print("Finding commit SHA for previous version " + prev_release_ver)
        for tag in repo_tags:
            if tag.name == prev_release_ver:
                prev_release_sha = tag.commit.sha
                #print(prev_release_sha)
    commit = repo.get_commit(sha=prev_release_sha)
    prev_release_commit_date=str(commit.commit.author.date.date())    #break

    if not commit:
        print("No starting point found via version tag or commit SHA")
        exit

    print("Enumerating Open PRs in master\n")
    print("- Retrieving Pull Request Issues from Github")
    search_string = f"repo:apache/cloudstack is:open is:pr"
    issues = gh.search_issues(search_string)
    wip_features = 0

    print("- Processing Open Pull Request Issues")
    for issue in issues:
        pr = issue.repository.get_pull(issue.number)
        label = []
        pr_num = str(pr.number)
        labels = pr.labels
        needed_labels = [type:bug, type:enhancement, type:experimental-feature, type:new-feature]
        if labels not in needed_labels:
            print("-- Found open PR : " + pr_num + " without recognised label")
            print("--- Looking for bug text")
            if = re.search('.*- [x] Bug fix *).*', issue['body']):
                issue.add_to_labels(*labels)
 
            if = re.search('.*- [x] Enhancement *).*', issue['body']):
                add label
            if = re.search('.*- [x] Breaking change *).*', issue['body']):
                add label
            if = re.search('.*- [x] New feature *).*', issue['body']):
                add label
            if = re.search('.*- [x] Cleanup *).*', issue['body']):
                add label





(fix or feature that would cause existing functionality to change)
(non-breaking change which adds functionality)
- [ ] Bug fix (non-breaking change which fixes an issue)
(improves an existing feature and functionality)
- [ ] Cleanup 

        reverted = re.match('^Revert "', thiscommit)
        if reverted:
            commitdatestr = commit['date']
            date_time_str = ' '.join(commitdatestr.split(" ")[:-1])
            commitdate = datetime.strptime(date_time_str, '%c').date()
            if commitdate > previous_commit_date:
                revertedcommit = re.search('.*This reverts commit ([A-Za-z0-9]*).*', commit['message'])









    print("\nEnumerating open PRs in master\n")

    print("- Retrieving Pull Request Issues from Github")
    search_string = f"repo:apache/cloudstack is:closed is:pr is:merged merged:>={prev_release_commit_date}"
    issues = gh.search_issues(search_string)
    features = 0
    fixes = 0
    uncategorised = 0

    print("\nProcessing Pull Request Issues\n")
    for issue in issues:
        pr = issue.repository.get_pull(issue.number)
        pr_commit_sha = pr.merge_commit_sha
        if pr_commit_sha in reverted_shas:
            print("- Skipping PR %s, its been reverted", pr.merge_commit_sha)
        else:
            label = []
            pr_num = str(pr.number)
            labels = pr.labels
            if [l.name for l in labels if l.name=='type:new-feature' or l.name=='type:enhancement']:
                features_table.add_row([pr_num, pr.title.strip(), "-", "-"]) 
                print("-- Found PR: " + pr_num + " with feature label")
                features += 1
            if [l.name for l in labels if l.name=='type:bug' or l.name=='BUG']:
                fixes_table.add_row([pr_num, pr.title.strip(), "-", "-"]) 
                print("-- Found PR: " + pr_num + " with fix label")
                fixes += 1
            else:
                print("-- Found PR: " + pr_num + " with no matching label")
                dontknow_table.add_row([pr_num, pr.title.strip(), "-", "-"])
                uncategorised += 1

    print("\nwriting tables")
    wip_features_table_txt = wip_features_table.get_string()
    fixes_table_txt = fixes_table.get_string()
    features_table_txt = features_table.get_string()
    dontknow_table_txt = dontknow_table.get_string()
    with open(prs_file ,"w") as file:
        file.write('\nWork in Progress Features & Enhancements\n\n')
        file.write(wip_features_table_txt)
        file.write('\n%s Features listed\n\n' % str(wip_features))
        file.write('New Features & Enhancements\n\n')
        file.write(features_table_txt)
        file.write('\n%s Features listed\n\nBug Fixes\n\n' % str(features))
        file.write(fixes_table_txt)
        file.write('\n%s Bugs listed\n\n' % str(fixes))
        file.write(dontknow_table_txt)
        file.write('\n%s uncategorised issues listed\n\n' % str(uncategorised))
    file.close()
    print(("\nTable has been output to %s\n\n" % prs_file))
