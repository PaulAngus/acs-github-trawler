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

import docopt
import json
from github import Github
import os.path
import re
import sys
from prettytable import PrettyTable


def load_config():
    """
    Parse the command line arguments and load in the optional config file values
    """
    args = docopt.docopt(__doc__)
    args['--update_labels'] = ''
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

def merge(primary, secondary):
    """
    Merge two dictionaries.
    Values that evaluate to true take priority over false values.
    `primary` takes priority over `secondary`.
    """
    return dict((str(key), primary.get(key) or secondary.get(key))
                for key in set(secondary) | set(primary))

def label_reconcile(label_string, text_string):

    global text_matched
    global labels_added
    global labels_removed

        
    print("existing")
    print(existing_label_names)

    search_string = '.*- \[x\] ' + text_string + ' .*'
    negative_search_string = '.*- \[ ?\] ' + text_string + ' .*'
    print('--- Looking for ' + text_string + ' in description')
    if re.search(search_string, str(issue.body)):
        print(text_string +" found in description")
        if label_string in existing_label_names:
            text_matched += 1
            print("*** " + text_string + " label matched")
        else:
            print("*** " + text_string + " label added")
            labels_to_add_table.add_row([pr_num, pr.title.strip(), label_string])
            labels_added += 1
            if update_labels:
                pr.add_to_labels(label_string)
    elif re.search(negative_search_string, str(issue.body)) and label_string in existing_label_names:
        print(label_string + " shouldn't be here - removing")
        labels_to_remove_table.add_row([pr_num, pr.title.strip(), label_string])
        labels_removed += 1
        if update_labels:
            pr.remove_from_labels(label_string)


# run the code...
if __name__ == '__main__':
    print('\nInitialising...\n\n')

    args = load_config()
#   repository details
    gh_token = args['--gh_token']
    gh = Github(gh_token)
    repo_name = args['--repo']
    branch = args['--branch']
    gh_base_url = args['--gh_base_url']
    draft_pr_label = "wip"
    update_labels = args['--update_labels']
    if update_labels != '':
        update_labels = bool(args['--update_labels'])
    else:
        update_labels = bool(False)

    repo = gh.get_repo(repo_name)
    labels_to_add_table = PrettyTable(["PR Number", "Title", "New Label"])
    issues_without_label_or_description_table = PrettyTable(["PR Number", "Title", "Type"]) 
    labels_to_remove_table = PrettyTable(["PR Number", "Title", "Wrong Label"])
    labels_file = "/tmp/labels"
    labels_added = 0
    updated_issues = 0
    unmatched_issues = 0
    labels_removed = 0


    print("Enumerating Open PRs in master\n")
    print("- Retrieving Pull Request Issues from Github")
    search_string = f"repo:paulangus/acs-github-trawler is:open is:pr"
    issues = gh.search_issues(search_string)

    print("- Processing Open Pull Request Issues/n")
    for issue in issues:
        existing_labels = []
        label = []
        existing_label_names = []
        label_names = {"type:bug": "Bug fix", "type:enhancement": "Enhancement", "type:experimental-feature": \
                      "Experimental feature", "type:new_feature": "New feature", "type:cleanup": "Cleanup", \
                      "type:breaking_change": "Breaking change"}
        label_matches = 0
        text_matched = 0
        pr = issue.repository.get_pull(issue.number)
        pr_num = str(pr.number)
        is_draft = pr.draft
        print("\n-- Checking pr#: " + pr_num + "\n")
        existing_labels = pr.labels
        print(str(issue.body))

        for label in existing_labels:
            existing_label_names.append(label.name)
        
        if is_draft:
            print(">>> PR is a draft")
            prtype = 'Draft PR'
            if draft_pr_label not in existing_label_names:
                print("*** Daft PR missing wip label - adding label")
                labels_to_add_table.add_row([pr_num, pr.title.strip(), "wip"])
                if update_labels:
                    pr.add_to_labels("wip")
            else:
                print("--- wip label found")
        if not is_draft:
            print(">>> PR is not a draft")
            prtype = 'PR'
            if draft_pr_label in existing_label_names:
                print("*** PR with incorrect wip label - removing label")
                labels_to_add_table.add_row([pr_num, pr.title.strip(), "Remove wip"])
                if update_labels:
                    pr.remove_from_labels("wip")

        for label_name in label_names:
            label_reconcile(label_name, label_names[label_name])

        if text_matched > 0:
            updated_issues += 1
        else:
            unmatched_issues += 1
            print("---- No text matched in description *** BAD BAD BAD ***")
            issues_without_label_or_description_table.add_row([pr_num, pr.title.strip(), prtype ])

        if label_matches == 1 and text_matched == 0:
            print("---- Required label found - no action required")
        elif label_matches > 0 and text_matched > 0:
            print("---- All fixed now")
        else:
            print("---- This one's a problem")

    print("\nwriting tables")
    labels_to_add_txt = labels_to_add_table.get_string()
    issues_without_label_or_description_txt = issues_without_label_or_description_table.get_string()
    with open(labels_file ,"w") as file:
        file.write('\nLabel updates to PRs\n\n')
        file.write(labels_to_add_txt)
        file.write('\n%s PRs Updated\n\n\n' % str(updated_issues))
        file.write('Issues without label and description\n')
        file.write(issues_without_label_or_description_txt)
        file.write('\n%s Unmatched PRs\n\n' % str(unmatched_issues))
    file.close()
    print(("\nTable has been output to %s\n\n" % labels_file))

