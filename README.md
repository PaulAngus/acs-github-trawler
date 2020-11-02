# acs-github-trawler

This script reads OPEN PRs and reconciles/reports on labels.
The [x] in the descriptions is teh source of truth.  If a label is found without the matching [x] in the description it will be reported as a mismatch.
'wip' will be added to draft PRs and removed from non-draft PRs


conf.txt:

{
	"--gh_token":"***********",
	"--prev_release_commit":"6f96b3b2b391a9b7d085f76bcafa3989d9832b4e",
	"--repo_name":"PaulAngus/acs-github-trawler",
	"--branch":"master",
	"--prev_release_ver":"4.14.0.0",
	"--update_labels": "True"
}


note:   'prev_release_commit' not currently required
        'prev_release_ver' not currently required

If update_labels is 'False' or not passed, script will report back but take no action

TODO

Carry out the same tasks for CLOSED PRs for next release.

