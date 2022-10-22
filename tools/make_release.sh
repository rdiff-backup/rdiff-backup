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

