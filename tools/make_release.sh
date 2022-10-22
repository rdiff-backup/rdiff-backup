#!/usr/bin/env bash

RELEASE="$1"

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
git commit -m "Preparing release ${RELEASE}"
git push --set-upstream origin ${CURR_BRANCH}

gh pr create \
	--assignee '@me' \
	--fill \
	--base master \
	--head ${CURR_BRANCH} \
	--repo rdiff-backup/rdiff-backup

# retrieve the Pull Request number

PR_NUMBER=$(gh pr list --author '@me' --head ericzolf-prepare-v2.1.3b0 \
	--json number --template '{{range .}}{{.number}}{{end}}')

# wait for Pull Request checks to be completed (and successful)

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
	[ ${PR_STATUS} != "COMPLETED" ] && sleep 10
done

if [ ${PR_CONCLUSION} != "SUCCESS" ]
then
	echo "PR #${PR_NUMBER} failed with ${PR_CONCLUSION}" >&2
	exit 3
fi

# check if it can be merged, else exit

PR_MERGE_STATE=$(gh pr view ${PR_NUMBER} --json mergeStateStatus,mergeable \
	--template '{{ .mergeStateStatus }}/{{ .mergeable }}')
if [ ${PR_MERGE_STATE} != "CLEAN/MERGEABLE" ]
then
	echo "PR #${PR_NUMBER} state is ${PR_MERGE_STATE}, exiting" 2>&1
	exit 2
fi
