#!/usr/bin/env bash
# call with $0 v1.2.3 ["commit messages"...]
# Require that the go-lang tool "gh" is installed

RELEASE="$1"
shift

if [[ "${RELEASE}" != v* ]]
then
	echo "Release must start with v like version" >&2
	exit 1
fi

# first check that the changelog has been properly updated

FIRST_ENTRY=$(grep '^== New in ' CHANGELOG.adoc | head -n1)

if ! echo ${FIRST_ENTRY} | grep -q " ${RELEASE} ([0-9-]*)"
then
	echo "Changelog doesn't look right with '${FIRST_ENTRY}' instead of release ${RELEASE} (with date)" >&2
	exit 1
fi

# then login to GitHub and grab the user's name

gh auth login --hostname github.com  # interactive login
GH_USER=$(gh auth status --show-token 2>&1 | sed -n -e 's/.*Logged in to github.com as \([^ ]*\) .*/\1/p')

# create a branch if necessary

CURR_BRANCH=$(git branch --show-current)
if [ ${CURR_BRANCH} == 'master' ]
then
	CURR_BRANCH=${GH_USER}-prepare-${RELEASE}
	git checkout -b ${CURR_BRANCH}
fi

# add, commit, push branch

git add CHANGELOG.adoc
if [ -n "$*" ]
then
	git commit -m "Preparing release ${RELEASE}

$(for line in "$@"; do echo ${line}; done)"
else
	git commit -m "Preparing release ${RELEASE}"
fi
git push --set-upstream origin ${CURR_BRANCH}

gh pr create \
	--assignee '@me' \
	--fill \
	--base master \
	--head ${CURR_BRANCH} \
	--repo rdiff-backup/rdiff-backup  # determines the following commands

sleep 5  # GitHub needs a bit of time to react

# retrieve the Pull Request number

PR_NUMBER=$(gh pr list --author '@me' --head ${GH_USER}-prepare-${RELEASE} \
	--json number --template '{{range .}}{{.number}}{{end}}')

# wait for Pull Request checks to be completed (and successful)

while [ "$(gh pr view ${PR_NUMBER} --json mergeStateStatus --template '{{ .mergeStateStatus }}')" == "BLOCKED" ]
do
	echo "PR #${PR_NUMBER} merge status: BLOCKED, waiting 20 more secs..."
	sleep 20
done

PR_STATUS="IN_PROGRESS"
while [ ${PR_STATUS} != "COMPLETED" ]
do
	PR_STATUS="COMPLETED"
	PR_CONCLUSION="SUCCESS"
	while read status conclusion
	do
		if [ "${status}" != "COMPLETED" ]
		then
			PR_STATUS=${status}
		else
			if [ "${conclusion}" != "SUCCESS" ]
			then
				PR_CONCLUSION=${conclusion}
			fi
		fi
	done < <(gh pr view ${PR_NUMBER} --json statusCheckRollup --template '{{ range .statusCheckRollup }}{{ .status }} {{ .conclusion }}
{{ end }}')
	if [ "${PR_STATUS}" != "COMPLETED" ]
	then
		echo "PR #${PR_NUMBER} checks status: ${PR_STATUS}, waiting 20 more secs..."
		sleep 20
	fi
done

if [ ${PR_CONCLUSION} != "SUCCESS" ]
then
	echo "PR #${PR_NUMBER} failed with ${PR_CONCLUSION}" >&2
	exit 2
fi

# check if it can be merged, else exit

PR_MERGE_STATE=$(gh pr view ${PR_NUMBER} --json mergeStateStatus,mergeable \
	--template '{{ .mergeStateStatus }}/{{ .mergeable }}')
if [ ${PR_MERGE_STATE} != "CLEAN/MERGEABLE" ]
then
	echo "PR #${PR_NUMBER} state is ${PR_MERGE_STATE}, exiting" 2>&1
	exit 3
fi

set -e  # exit immediately if something goes wrong

gh pr review ${PR_NUMBER} --comment \
	--body "Automatically created and merged by $(basename $0)"

gh pr merge ${PR_NUMBER} --auto --squash --delete-branch

sleep 5

git checkout master
git pull --prune
git tag ${RELEASE}
git push --tags
