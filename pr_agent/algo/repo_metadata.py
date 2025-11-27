"""
Utility functions for reading repository metadata files (e.g., AGENTS.MD, QODO.MD, CLAUDE.MD)
and incorporating them into PR review context.
"""
import json
from typing import Optional
from pr_agent.config_loader import get_settings
from pr_agent.git_providers.git_provider import GitProvider
from pr_agent.log import get_logger


def get_repo_metadata_content(git_provider: GitProvider) -> str:
    """
    Read repository metadata files from the PR's head branch and return their combined content.
    
    This function reads markdown files specified in the configuration from any path in the repository
    (e.g., "AGENTS.MD", "docs/standards.md", "security/compliance.md", "coding-standards.md").
    Files can be located anywhere in the repository - users specify the path from the project root.
    The content is combined and returned as a single string that provides context for PR reviews,
    such as coding standards, security guidelines, specification compliance, best practices, etc.
    
    Args:
        git_provider: The git provider instance for the current PR
        
    Returns:
        A string containing the combined content of all found metadata files with clear formatting,
        or an empty string if the feature is disabled or no files are found.
    """
    # Check if repo metadata feature is enabled
    if not get_settings().get("config.add_repo_metadata", False):
        get_logger().debug("Repo metadata feature is disabled")
        return ""
    
    # Get the list of metadata files to read (can be paths from project root, e.g., "docs/standards.md")
    metadata_file_list = get_settings().get("config.add_repo_metadata_file_list", [])
    
    # Handle case where env var is passed as JSON string (e.g., from GitHub Actions)
    if isinstance(metadata_file_list, str):
        try:
            metadata_file_list = json.loads(metadata_file_list)
        except (json.JSONDecodeError, ValueError):
            # If it's not valid JSON, treat as single file path
            metadata_file_list = [metadata_file_list] if metadata_file_list.strip() else []
    
    if not metadata_file_list:
        get_logger().debug("No metadata files specified in add_repo_metadata_file_list")
        return ""
    
    # Get the PR branch (head branch)
    try:
        pr_branch = git_provider.get_pr_branch()
        if not pr_branch:
            get_logger().warning("Could not determine PR branch for reading metadata files")
            return ""
    except Exception as e:
        get_logger().warning(f"Error getting PR branch: {e}")
        return ""
    
    # Collect content from all metadata files
    metadata_contents = []
    files_found = []
    files_not_found = []
    
    for metadata_file in metadata_file_list:
        # Normalize the file path (remove leading slash if present, handle relative paths)
        file_path = metadata_file.lstrip('/').strip()
        if not file_path:
            continue
            
        try:
            # Try to read the file from the PR's head branch
            # Most providers have a get_pr_file_content method that accepts paths
            if hasattr(git_provider, 'get_pr_file_content'):
                content = git_provider.get_pr_file_content(file_path, pr_branch)
                if content and content.strip():
                    # Format the content with clear context about what this file represents
                    # Use the full path in the header for clarity
                    formatted_content = f"### Repository Metadata File: `{file_path}`\n\n{content.strip()}\n"
                    metadata_contents.append(formatted_content)
                    files_found.append(file_path)
                    get_logger().info(f"Successfully read metadata file: {file_path}")
                else:
                    files_not_found.append(file_path)
                    get_logger().debug(f"Metadata file not found or empty: {file_path}")
            else:
                # Fallback: try to clone the repo and read the file
                get_logger().debug(f"Provider {type(git_provider).__name__} does not have get_pr_file_content, trying alternative method")
                content = _read_metadata_file_alternative(git_provider, file_path, pr_branch)
                if content and content.strip():
                    formatted_content = f"### Repository Metadata File: `{file_path}`\n\n{content.strip()}\n"
                    metadata_contents.append(formatted_content)
                    files_found.append(file_path)
                else:
                    files_not_found.append(file_path)
        except Exception as e:
            get_logger().warning(f"Error reading metadata file {file_path}: {e}")
            files_not_found.append(file_path)
    
    if not metadata_contents:
        if files_not_found:
            get_logger().info(f"Repo metadata feature enabled but no metadata files found: {files_not_found}")
        return ""
    
    # Combine all metadata files with a clear header explaining their purpose
    header = "## 📋 Repository-Specific Rules and Guidelines\n\n"
    header += "The following content has been loaded from repository metadata files. "
    header += "These files contain important context such as coding standards, security guidelines, "
    header += "specification compliance requirements, best practices, and other rules that should be "
    header += "considered when reviewing this PR. Please use this information to ensure the PR "
    header += "complies with the repository's established standards.\n\n"
    header += "---\n\n"
    
    combined_content = header + "\n\n---\n\n".join(metadata_contents)
    
    get_logger().info(f"Successfully loaded repo metadata from {len(files_found)} file(s): {files_found}")
    
    return combined_content


def _read_metadata_file_alternative(git_provider: GitProvider, file_path: str, branch: str) -> str:
    """
    Alternative method to read metadata files by cloning the repository.
    This is a fallback when get_pr_file_content is not available.
    
    Note: This method clones the default branch, not the PR branch. For best results,
    providers should implement get_pr_file_content to read from the PR's head branch.
    """
    try:
        from tempfile import TemporaryDirectory
        import os
        
        repo_url = git_provider.get_git_repo_url(git_provider.get_pr_url())
        if not repo_url:
            return ""
        
        with TemporaryDirectory() as tmp_dir:
            cloned_repo = git_provider.clone(repo_url, tmp_dir, remove_dest_folder=False)
            if not cloned_repo:
                return ""
            
            # Normalize path and join with cloned repo root
            # file_path is already normalized (no leading slash) from the calling function
            file_full_path = os.path.join(cloned_repo.path, file_path)
            
            # Normalize the path to handle any path separators correctly
            file_full_path = os.path.normpath(file_full_path)
            
            if os.path.exists(file_full_path) and os.path.isfile(file_full_path):
                with open(file_full_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                get_logger().debug(f"File not found at path: {file_full_path} (looking for: {file_path})")
    except Exception as e:
        get_logger().debug(f"Alternative method failed to read {file_path}: {e}")
    
    return ""

