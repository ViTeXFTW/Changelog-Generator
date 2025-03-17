from changelogger import Changelogger
from dotenv import load_dotenv
from github import Github, Repository
import argparse
import os
from changelogger import ChangelogEntryPosition

# Load environment variables from a .env file
load_dotenv()
# Access the GitHub token from the environment
GH_TOKEN = os.getenv("GH_TOKEN")

def authenticate() -> tuple[Github, Repository.Repository]:
    """
    Authenticate with the GitHub API.

    :param token: The GitHub token.
    :return: A tuple containing the GitHub object and the repository object.
    """

    global ghub, repository
    try:
        ghub = Github(os.getenv("GH_TOKEN"))
        repository = ghub.get_repo(os.getenv("REPO_NAME"))
        return ghub, repository
    except:
        print("Authentication failed.")
        return False


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Generate a changelog for a GitHub repository.")

    parser.add_argument("-b", "--branch", type=str, help="The branch to generate the changelog from.", default="main")
    parser.add_argument('-f', "--file-name", type=str, help="The name of the changelog file.", default="CHANGELOG.md")
    parser.add_argument("-pr", "--use-pull-requests", action="store_true", help="Use pull requests to generate the changelog.", default=True)
    parser.add_argument("-c", "--use-commits", action="store_true", help="Use commit messages to generate the changelog.", default=True)
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output.", default=False)
    parser.add_argument("--insert-position", type=str, help="The position to insert the changelog entry.", default="above_previous", choices=[position.value for position in ChangelogEntryPosition])
    parser.add_argument("--commit-message", type=str, help="The commit message to use when updating the changelog.", default=Changelogger.COMMIT_MESSAGE)

    parser.add_argument("-r", "--release", action="store_true", help="Generate a release changelog.", default=False)
    parser.add_argument("--draft", action="store_true", help="Mark the release as a draft. Requires release is true", default=False)
    parser.add_argument("--prerelease", action="store_true", help="Mark the release as a prerelease. Requires release is true", default=False)

    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run.", default=False)

    args = parser.parse_args()

    if not args.release and (args.draft or args.prerelease):
        parser.error("--draft and --prerelease require --release to be set.")

    ghub, repo = authenticate()
    
    changelogger = Changelogger(repo,
                                args.branch,
                                args.file_name,
                                args.use_pull_requests,
                                args.use_commits,
                                args.release,
                                args.draft,
                                args.prerelease,
                                ChangelogEntryPosition(args.insert_position),
                                args.commit_message,
                                dry_run=args.dry_run)
    
    changelogger.create_new_changelog_entry()