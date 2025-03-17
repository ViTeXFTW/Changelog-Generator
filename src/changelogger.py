from enum import Enum, auto
from github import Repository, Commit, PullRequest, InputGitAuthor
from loguru import logger
from datetime import datetime
import sys, re


class ChangelogEntryPosition(Enum):
    ABOVE_PREVIOUS = "above_previous"
    BELOW_PREVIOUS = "below_previous"
    TOP = "top"
    BOTTOM = "bottom"

class Changelogger:
    """
    Class to generate a changelog from a git repository.
    
    Uses the format:
    \# Changelog

    \#\# [v#.#.#] - (YYYY-MM-DD)  
    \- Commit message  
    \- PR title

    \#\# [initial release] - (YYYY-MM-DD)
    """

    MAX_DEBUG_LENGTH = 50
    COMMIT_MESSAGE = "chore(changelog): update changelog and create release [skip ci]"
    CI_AUTHOR = {
        "name": "GitHub Actions",
        "email": "github-actions[bot]@users.noreply.github.com"
    }

    class ChangelogEntryType:
        BREAKING_CHANGE = "breaking change"
        FEATURE = ["feature", "feat"]
        FIX = "fix"

        @classmethod
        def all(cls) -> list[str]:
            types = []
            for attr in dir(cls):
                if attr.startswith("_"):
                    continue
                value = getattr(cls, attr)
                if not callable(value):
                    if isinstance(value, list):
                        types.extend(value)
                    else:
                        types.append(value)
            return types

    changelog_regex = re.compile(r'##\s*(v\d+\.\d+\.\d+)\s*-\s*\((\d{4}-\d{2}-\d{2})\)')
    

    def __init__(self,
                 repository: Repository.Repository,
                 ref: str = "main",
                 changelog_filename = "CHANGELOG.md",
                 use_commits = True,
                 use_pull_requests = True,
                 release = False,
                 draft = False,
                 prerelease = False,
                 entry_position = ChangelogEntryPosition.ABOVE_PREVIOUS,
                 custom_commit_message = COMMIT_MESSAGE,
                 ci_author = CI_AUTHOR,
                 dry_run = False):
        """
        Initialize the Changelogger.

        :param repository: The repository to generate the changelog for
        :param ref: The branch to generate the changelog for
        :param changelog_filename: The filename of the changelog
        :param draft: Create the release as a draft
        :param prerelease: Create the release as a prerelease
        :param entry_position: The position to insert the new entry
        :param custom_commit_message: The commit message to use
        :param ci_author: The author to use for the commit
        """
        self.__dry_run = dry_run

        self.__repository = repository
        self.__ref = ref
        self.__filename_changelog = changelog_filename
        self.__use_commits = use_commits
        self.__use_pull_requests = use_pull_requests
        self.__release = release
        self.__is_draft = draft
        self.__is_prerelease = prerelease
        self.__entry_position = entry_position
        self.__commit_message = custom_commit_message
        self.__ci_author = InputGitAuthor(ci_author["name"], ci_author["email"])

    def _setup_logging(self):
        logger.remove()
        logger.add(sys.stderr, level="INFO")

    def _get_previous_release_info(self, changelog: str) -> tuple[str, str]:
        """
        Use the in repository changelog to get the latest release.
        Looks for '##' in the changelog, parse through regex to get the version and date.
        
        :param changelog: The changelog file to parse
        :return: Tuple of the version and date
        """
        
        try:
            lines = changelog.splitlines()
            header_lines: list[str] = []

            for line in lines:
            # If existing release exists, use it
                if line.startswith("##"):
                    header_lines.append(line)
                    match = self.changelog_regex.match(line)
                    if match:
                        logger.info(f"Found existing release: {match.group(1)} - {match.group(2)}")
                        return match.group(1), datetime.strptime(match.group(2), "%Y-%m-%d").strftime("%Y-%m-%d")
            
            logger.warning("No existing release found, checking for initial release date")

            # Fallback check for initial release entry
            for line in header_lines:
                if "initial release" in line.lower():
                    logger.info(f"Found initial release: {line}")
                    match = re.search(r'\(?(\d{4}-\d{2}-\d{2})\)?', line)
                    if match:
                        logger.info(f"Date found from initial release: {match.group(1)}")
                        return "v0.0.0", datetime.strptime(match.group(1), "%Y-%m-%d").strftime("%Y-%m-%d")

            logger.warning("No initial release found, using current date")
            return "v0.0.0", datetime.now().strftime("%Y-%m-%d")
        except Exception as e:
            logger.error(f"Error parsing changelog: {e}")
            return None, None
        


    
    def _get_commits(self, since: str, until: str = None) -> list[Commit.Commit]:
        """
        Get all commits between two dates.
        
        :param since: The start date
        :param until: The end date, defaults to now
        :return: List of commits
        """
        found_commits: list[Commit.Commit] = []

        # If no until date is provided, use the current date
        if not until:
            until = datetime.now().strftime("%Y-%m-%d")

        since = datetime.strptime(since, "%Y-%m-%d")
        until = datetime.strptime(until, "%Y-%m-%d")

        # Get commits that contains entries in ChangelogEntryType
        try:
            commits = self.__repository.get_commits(since=since, until=until, sha=self.__ref)
            for commit in commits:
                for type in self.ChangelogEntryType.all():
                    if type in commit.commit.message.lower():
                        logger.debug(f"Found commit: {commit.commit.message[:self.MAX_DEBUG_LENGTH]}")
                        found_commits.append(commit)
            
            logger.info(f"Found {len(found_commits)} commits")

        except Exception as e:
            logger.error(f"Error getting commits: {e}")
            if not found_commits:
                logger.warning("No commits found")
            else:
                logger.warning("Commits found, continuing...")            
        
        # Return the found commits
        return found_commits



    def _get_pull_requests(self, since: str, until: str = "") -> list[PullRequest.PullRequest]:
        """
        Get all pull requests between two dates.
        
        :param since: The start date
        :param until: The end date
        :return: List of pull requests
        """
        found_prs: list[PullRequest.PullRequest] = []

        # If no until date is provided, use the current date
        if not until:
            until = datetime.now().strftime("%Y-%m-%d")

        # Get pull requests that contains entries in ChangelogEntryType
        try:
            prs = self.__repository.get_pulls(state="closed",
                                              sort="updated",
                                              direction="desc",
                                              base=self.__ref)
            
            for pr in prs:
                for type in self.ChangelogEntryType:
                    if type in pr.title.lower():
                        logger.debug(f"Found PR: {pr.title[:self.MAX_DEBUG_LENGTH]}")
                        found_prs.append(pr)
            
            logger.info(f"Found {len(found_prs)} pull requests")        

        except Exception as e:
            logger.error(f"Error getting pull requests: {e}")
            if not found_prs:
                logger.warning("No pull requests found")
            else:
                logger.warning("Pull requests found, continuing...")

        # Return the found pull requests
        return found_prs

    def _bump_version(self, version: str, additions: list[PullRequest.PullRequest | Commit.Commit]) -> str:
        """
        Bump the version based on the additions.
        
        :param version: The current version
        :param additions: List of commits or pull requests
        :return: The new version
        """
        
        if version.startswith("v"):
            version = version[1:]

        major_bump, minor_bump, patch_bump = False, False, False
        major, minor, patch = map(int, version.split("."))

        for item in additions:
            if isinstance(item, PullRequest.PullRequest):
                content = item.title.lower() + '\n' + item.body.lower()
            elif isinstance(item, Commit.Commit):
                content = item.commit.message.lower()
            else:
                logger.warning(f"Unknown item type: {type(item)}")
                continue

            if self.ChangelogEntryType.BREAKING_CHANGE in content:
                major_bump = True
            elif any(feat in content for feat in self.ChangelogEntryType.FEATURE):
                minor_bump = True
            elif self.ChangelogEntryType.FIX in content:
                patch_bump = True
            else:
                logger.warning(f"Unknown content type: {content}")

        if major_bump:
            major += 1
        elif minor_bump:
            minor += 1
        elif patch_bump:
            patch += 1
        else:
            logger.warning("No bump detected")
            return version
        
        return f"v{major}.{minor}.{patch}"

    def _create_new_entry(self, new_version: str, additions: list[PullRequest.PullRequest | Commit.Commit], custom_date: str = None) -> str:
        """
        Create a new entry for the changelog.
        
        :param new_version: The new version
        :param additions: List of commits or pull requests
        :param custom_date: The date to use for the entry, if not provided, use the current date
        :return: The new entry
        """
        
        if not custom_date:
            custom_date = datetime.now().strftime("%Y-%m-%d")

        entry_lines = [f"## {new_version} - ({custom_date})"]

        for item in additions:
            if isinstance(item, PullRequest.PullRequest):
                entry_lines.append(f"- {item.title}")
            elif isinstance(item, Commit.Commit):
                entry_lines.append(f"- {item.commit.message.splitlines()[0]}")

        return "\n".join(entry_lines)


    def _create_updated_changelog(self, new_entry: str, changelog: str) -> str:
        """
        Update the changelog with the new entry.
        
        :param new_entry: The new entry
        :param changelog: The current changelog
        :return: The updated changelog
        """

        position = self.__entry_position
        
        # Insert the new entry based on the position
        match(position):
            case ChangelogEntryPosition.TOP:
                return new_entry + changelog
            
            case ChangelogEntryPosition.BOTTOM:
                return changelog + new_entry
            
            case ChangelogEntryPosition.ABOVE_PREVIOUS:
                # Find first '##' line and insert above
                lines = changelog.splitlines()
                for i, line in enumerate(lines):
                    if line.startswith("##"):
                        lines.insert(i, new_entry)
                        return "\n".join(lines)
                return new_entry + "\n" + changelog
            
            case ChangelogEntryPosition.BELOW_PREVIOUS:
                # Find first '##' line and insert below
                lines = changelog.splitlines()
                for i, line in enumerate(lines):
                    if line.startswith("##"):
                        lines.insert(i + 1, new_entry)
                        return "\n".join(lines)
                return changelog + new_entry
            
            case _:
                logger.error(f"Unknown position: {position}, no changes made")
                return changelog

    def _publish_new_changelog(self, repository: Repository.Repository, changelog: str, changelog_sha: str) -> bool:
        """
        Publish the new changelog to the repository.
        
        :param repository: The repository to publish to
        :param changelog: The new changelog
        :return: True if successful, False otherwise
        """

        try:
            repository.update_file(self.__filename_changelog,
                                   self.__commit_message,
                                   changelog,
                                   changelog_sha,
                                   branch=self.__ref,
                                   author=self.__ci_author,
                                   committer=self.__ci_author)
            logger.success("Changelog updated")
            return True
        except Exception as e:
            logger.error(f"Error updating changelog: {e}")
            return False


    def _create_new_release(self, repository: Repository.Repository, new_version: str) -> bool:
        """
        Create a new release in the repository.
        
        :param repository: The repository to create the release in
        :param new_version: The new version
        :return: True if successful, False otherwise
        """
        
        try:
            repository.create_git_release(tag=new_version,
                                          name=new_version,
                                          message=f"Release {new_version}",
                                          target_commitish=self.__ref,
                                          draft=self.__is_draft,
                                          prerelease=self.__is_prerelease)
            logger.success(f"Release {new_version} created")
            return True
        except Exception as e:
            logger.error(f"Error creating release: {e}")
            return False


    def create_new_changelog_entry(self) -> bool:
        """
        Create new changelog entry, update changelog and publish to repository.
        
        :param repository: The repository to create the changelog entry for
        :return: True if successful, False otherwise
        """
        
        # Get remote changelog file
        changelog_content = self.__repository.get_contents(self.__filename_changelog)
        
        if not changelog_content:
            logger.error("Error getting changelog file, has it been pushed?")
            return False
        
        changelog = changelog_content.decoded_content.decode("utf-8")
        changelog_sha = changelog_content.sha
        
        previous_version, previous_date = self._get_previous_release_info(changelog)
        
        # Get the commits and pull requests
        if self.__use_commits:
            commits = self._get_commits(previous_date)
        
        if self.__use_pull_requests:
            pull_requests = self._get_pull_requests(previous_date)
        
        entries = commits + pull_requests
        if not entries and not self.__dry_run:
            logger.error("No entries found, returning")
            return False

        # Bump the version
        new_version = self._bump_version(previous_version, entries)
        
        # Create the new entry
        new_entry = self._create_new_entry(new_version, entries)
        
        # Update the changelog
        updated_changelog = self._create_updated_changelog(new_entry, changelog)
        
        # Publish the new changelog
        if self.__dry_run:
            logger.info(f"New version: {new_version}")
            logger.info(f"New entry: {new_entry}")
            logger.info(f"Updated changelog: {updated_changelog}")
            logger.success("Dry run enabled, skipping publish")
            return True
        
        if not self._publish_new_changelog(self.__repository, updated_changelog, changelog_sha):
            return False
        
        # Create a new release
        if self.__release:
            res = self._create_new_release(self.__repository, new_version)
            if not res:
                return False
        
        return True