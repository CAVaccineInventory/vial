#!/usr/bin/env bash

set -eu
DEPLOY_BRANCH=production
DEPLOY_FROM=origin/main

if [ -n "$(git status --untracked-files=no --porcelain)" ]; then
	echo "Untracked changes in local files -- aborting!"
	echo
	echo "For simplicity, this manipulates your working tree to do"
	echo "the merge; this requires a clean working copy.  Stash your"
	echo "changes and try again."
	exit 1
fi

# Make sure we have the most up-to-date main
git fetch --quiet origin

# First, a couple safety checks:

# First, verify that prod's tree is identical its most recent merge-base with
# main; that is, it has no changes that were not released on `main`.
ORIGIN_DEPLOY="origin/$DEPLOY_BRANCH"
MERGE_BASE=$(git merge-base "$DEPLOY_FROM" "$ORIGIN_DEPLOY")
if ! git diff "$MERGE_BASE" "$ORIGIN_DEPLOY" --exit-code; then
	echo "$DEPLOY_BRANCH tree has diverged from what was released on main!"
	echo
	git --no-pager diff --stat "$MERGE_BASE" "$ORIGIN_DEPLOY"
	echo
	git --no-pager log --no-decorate --oneline "$ORIGIN_DEPLOY" "^$DEPLOY_FROM" --max-parents=1
	exit 1
fi

# Second, verify that prod has no commits, besides merge commits, that
# are not on `main`.  Given the above check, this is only possible if
# there are changes that are a net no-change result, which would be
# odd.
if [ 0 -ne "$(git rev-list "$ORIGIN_DEPLOY" "^$DEPLOY_FROM" --max-parents=1 | wc -l)" ]; then
	echo "$DEPLOY_BRANCH contains non-merge commits that are not in main!"
	echo
	git --no-pager log --no-decorate --oneline "$ORIGIN_DEPLOY" "^$DEPLOY_FROM" --max-parents=1
	exit 1
fi

echo
echo "You are about to deploy the following commits:"
echo '```'
git --no-pager log --no-decorate --oneline --reverse "$DEPLOY_FROM" "^$ORIGIN_DEPLOY"
echo '```'

echo
echo "Type 'yes' to confirm they look right, and that you have gotten a :thumbsup: from #sysops:"
read -r VERIFY
if [ "$VERIFY" != "yes" ]; then
	exit 1
fi

# So we don't create, or rely on the state of a local "production" branch,
# work on a detached HEAD
CURRENT_BRANCH=$(git branch --show-current)
echo "Checking out detached $DEPLOY_BRANCH..."
git checkout --detach "$ORIGIN_DEPLOY"
echo
echo

# Always create a merge commit, as a marker of what was deployed at
# once.
echo "Merging main..."
git merge --no-edit --no-ff "$DEPLOY_FROM"
echo
echo

# Push the newly-generated merge commit
echo "Pushing new $DEPLOY_BRANCH to origin..."
git push origin "HEAD:refs/heads/$DEPLOY_BRANCH" || true
echo
echo

echo "Switching back to $CURRENT_BRANCH..."
git -c advice.detachedHead=false checkout "$CURRENT_BRANCH"
echo
echo

echo "Done!"
