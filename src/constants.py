from dotenv import load_dotenv
from github import Github, Repository
import os

# Load environment variables from a .env file
load_dotenv()
# Access the GitHub token from the environment
GH_TOKEN = os.getenv("GH_TOKEN")

REPO_NAME = "ViTeXFTW/Changelog-Generator"
RELEASE_BRANCH = "main"
CI_AUTHOR = {
    "name": "GitHub Actions",
    "email": "github-actions[bot]@users.noreply.github.com"  
}

CHANGELOG_INITIAL_CONTENT = "# Changelog\n\nAll notable changes to this project will be documented in this file.\n\nThe format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).\n\n"
MAX_COMMIT_HEADER_LENGTH = 100
SEMANTIC_VERSIONING_TYPES = ["breaking change", "feat", "feature", "fix"]

def authenticate() -> tuple[Github, Repository.Repository]:
    """
    Authenticate with the GitHub API.
    
    :return: A tuple containing the GitHub object and the repository object.
    """
    
    global ghub, repository
    try:
        ghub = Github(GH_TOKEN)
        repository = ghub.get_repo(REPO_NAME)
        return ghub, repository
    except:
        print("Authentication failed.")
        return False