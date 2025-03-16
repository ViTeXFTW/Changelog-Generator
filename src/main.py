from github import PullRequest, Commit
import argparse
from loguru import logger
import re
from datetime import datetime
from constants import RELEASE_BRANCH, CHANGELOG_INITIAL_CONTENT, MAX_COMMIT_HEADER_LENGTH, authenticate

# Meta information
CHANGELOG_FILE = "CHANGELOG.md"
COMMIT_MESSAGE = "chore(changelog): update changelog and create release"

ghub, repository = authenticate()

def parse_release_line(line: str) -> dict:
    """
    Parse a changelog release line to extract version and release date.
    
    :param line: A line from the changelog file.
    :return: A dictionary with version and release_date, or None if parsing fails.
    """
    match = re.match(r'##\s*(v[\d\.]+)\s*\((\d{4}-\d{2}-\d{2})\)$', line)
    if match:
        version = match.group(1)
        date_str = match.group(2)
        release_date = datetime.strptime(date_str, '%Y-%m-%d')
        return {"version": version, "release_date": release_date}
    return None

def get_latest_release() -> dict:
    """
    Get the latest version information from the changelog file.
    Looks for a header line in the format:
      ## v1.2.3 (YYYY-MM-DD)
    
    :return: A dictionary with latest_version and latest_release_date.
    """
    try:
        current_content = repository.get_contents(CHANGELOG_FILE, ref=RELEASE_BRANCH)
        decoded = current_content.decoded_content.decode("utf-8")
        lines = decoded.splitlines()
        for line in lines:
            if line.startswith("##"):
                parsed = parse_release_line(line)
                if parsed:
                    logger.info(f"Found version {parsed['version']} with date {parsed['release_date']} in changelog.")
                    return {"latest_version": parsed["version"], "latest_release_date": parsed["release_date"]}
                else:
                    # Fallback if format doesn't match: use the header as version and minimal date.
                    version = line.replace("##", "").strip()
                    logger.warning(f"Found version {version} in changelog without date format.")
                    return {"latest_version": version, "latest_release_date": datetime.min}
        logger.warning("No release version found in changelog.")
        return None
    except Exception as e:
        logger.warning(f"Changelog file not found or unreadable: {e}")
        return None


def get_commits_since(release_date: datetime) -> list[Commit.Commit]:
    commits: list[Commit.Commit] = []
    try:
        for commit in repository.get_commits(since=release_date, sha=RELEASE_BRANCH):
            logger.info(f"Commit: {commit.commit.message}")
            if not commit.commit.message.startswith("Merge"):
                commits.append(commit)
        logger.info(f"Found {len(commits)} commits since last release.")
    except:
        logger.warning("Failed to retrieve commits.")
    return commits

def get_merged_prs(release_date: datetime) -> list[PullRequest.PullRequest]:
    merged_prs: list[PullRequest.PullRequest] = []
    pulls = repository.get_pulls(state="closed", base=RELEASE_BRANCH)
    for pr in pulls:
        if pr.merged_at and pr.merged_at > release_date:
            # PaginatedList of pull request
            logger.info(f"PR: {pr.title}")
            merged_prs.append(pr)
    
    logger.info(f"Found {len(merged_prs)} merged PRs since last release.")
    return merged_prs

def calculate_new_version(current_version: str, items: list) -> str:
    major_bump = False
    minor_bump = False
    patch_bump = False

    for item in items:
        if isinstance(item, PullRequest.PullRequest):
            content = (item.title + "\n" + (item.body or "")).lower()
        elif isinstance(item, Commit.Commit):
            content = item.commit.message.lower()
        else:
            continue

        if "breaking change" in content:
            major_bump = True
        elif "feat" in content or "feature" in content:
            minor_bump = True
        elif "fix" in content:
            patch_bump = True
            
    try:
        if current_version.startswith("v"):
            major_num, minor_num, patch_num = map(int, current_version.strip("v").split("."))
        else:
            major_num, minor_num, patch_num = 0, 0, 0
    except:
        logger.warning("Invalid version format.")
        return None
    
    if major_bump:
        return f"v{major_num + 1}.0.0"
    elif minor_bump:
        return f"v{major_num}.{minor_num + 1}.0"
    elif patch_bump:
        return f"v{major_num}.{minor_num}.{patch_num + 1}"
    else:
        return current_version
    
def update_changelog(new_entry: str, dry_run = False) -> str:
    try:
        current_content = repository.get_contents(CHANGELOG_FILE, ref=RELEASE_BRANCH)
        decoded = current_content.decoded_content.decode("utf-8")
        # Split the existing changelog into lines
        lines = decoded.splitlines()
        # Find the index of the first release entry (lines starting with "##")
        insert_index = 0
        for i, line in enumerate(lines):
            if line.startswith("##"):
                insert_index = i
                break
        else:
            insert_index = len(lines)
        
        # Insert new_entry just before the first release entry, maintaining header
        updated_lines = lines[:insert_index] + [new_entry, ""] + lines[insert_index:]
        updated_content = "\n".join(updated_lines)
        
        if dry_run:
            logger.info("DRY RUN, FULL CHANGELOG: ")
            logger.info(updated_content)
        else:
            repository.update_file(current_content.path, COMMIT_MESSAGE, updated_content, current_content.sha, branch=RELEASE_BRANCH)
            logger.success("Changelog updated successfully.")
            return updated_content
    except:
        if dry_run:
            logger.info("DRY RUN, COULD NOT UPDATE CHANGELOG.")
            return ""
        else:
            logger.warning("Failed to update the changelog.")
            try:
                logger.info("Attempting to create a new file...")
                content = CHANGELOG_INITIAL_CONTENT + "\n" + new_entry + "\n\n## Initial Release\n\n### Added\n\n- Initial release\n"
                repository.create_file(CHANGELOG_FILE, COMMIT_MESSAGE, content, branch=RELEASE_BRANCH)
                logger.success("Changelog created successfully.")
                return new_entry
            except:
                logger.warning("Failed to create the changelog.")
                return ""

def create_release(new_version: str) -> bool:
    try:
        repository.create_git_release(
            tag=new_version,
            name=new_version,
            message="Release " + new_version,
            target_commitish=RELEASE_BRANCH
        )
        logger.success("Release created successfully.")
        return True
    except:
        logger.warning("Cannot create the release.")
        return False

# Begin the script

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Generate changelog using merged PRs or commits or both"
    )
    
    parser.add_argument(
        "-p", "--pr",
        action="store_true",
        default=True,
        help="Use merged PRs to generate changelog"
    )

    parser.add_argument(
        "-c", "--commit",
        action="store_true",
        default=False,
        help="Use commits to generate changelog"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="Print verbose output"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run the script without making any changes"
    )

    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN. GOING IN DRY!")

    if not authenticate():
        logger.error("Authentication failed. Exiting...")
        exit(0)

    release_info = get_latest_release()
    if not release_info:
        logger.error("No releases found. Exiting...")
        exit(1)
        
    latest_version = release_info["latest_version"]
    logger.info("Latest version: " + latest_version)

    items: list[PullRequest.PullRequest | Commit.Commit] = []
    if args.pr:
        merged_prs = get_merged_prs(release_info["latest_release_date"])
        items.extend(merged_prs)
        if not merged_prs:
            logger.info("No merged PRs found.")

    if args.commit:
        commits = get_commits_since(release_info["latest_release_date"])
        items.extend(commits)
        if not commits:
            logger.info("No commits found.")


    new_version = calculate_new_version(latest_version, items)
    if not new_version:
        logger.error("Invalid version format. Exiting...")
        exit(3)
        
    logger.info("New version: " + new_version)

    changelog_entry = f"## {new_version} ({datetime.now().strftime('%Y-%m-%d')})\n"
    for pr in merged_prs:
        changelog_entry += f"- {pr.title} (#{pr.number})\n"

    for commit in commits:
        # Add commit message to changelog, unless it is longer than 100 chars

        commit_title = commit.commit.message.splitlines()[0]

        if len(commit_title) > MAX_COMMIT_HEADER_LENGTH:
            commit_title = commit_title[:MAX_COMMIT_HEADER_LENGTH] + "..."
        
        changelog_entry += f"- {commit_title} ({commit.sha[:7]})\n"
        
    logger.info("Changelog entry generated:\n" + changelog_entry)

    if args.dry_run:
        logger.success("Dry run completed.")
        exit(0)

    if not update_changelog(changelog_entry):
        logger.error("Failed to update the changelog.")
        exit(4)

    create_release(new_version)

    logger.success("Done.")