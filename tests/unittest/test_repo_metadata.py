"""
Unit tests for pr_agent/algo/repo_metadata.py
Tests the functionality of reading repository metadata files and incorporating them into PR review context.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from pr_agent.algo.repo_metadata import get_repo_metadata_content, _read_metadata_file_alternative


class TestGetRepoMetadataContent:
    """Test cases for get_repo_metadata_content function"""

    def test_feature_disabled(self, monkeypatch):
        """Test that empty string is returned when feature is disabled"""
        # Arrange
        git_provider = Mock()
        monkeypatch.setattr('pr_agent.algo.repo_metadata.get_settings', 
                          lambda: Mock(get=lambda key, default=None: False if key == "config.add_repo_metadata" else default))
        
        # Act
        result = get_repo_metadata_content(git_provider)
        
        # Assert
        assert result == ""

    def test_no_metadata_files_specified(self, monkeypatch):
        """Test that empty string is returned when no metadata files are specified"""
        # Arrange
        git_provider = Mock()
        settings_mock = Mock()
        settings_mock.get = lambda key, default=None: {
            "config.add_repo_metadata": True,
            "config.add_repo_metadata_file_list": []
        }.get(key, default)
        monkeypatch.setattr('pr_agent.algo.repo_metadata.get_settings', lambda: settings_mock)
        
        # Act
        result = get_repo_metadata_content(git_provider)
        
        # Assert
        assert result == ""

    def test_pr_branch_not_available(self, monkeypatch):
        """Test that empty string is returned when PR branch cannot be determined"""
        # Arrange
        git_provider = Mock()
        git_provider.get_pr_branch.return_value = None
        
        settings_mock = Mock()
        settings_mock.get = lambda key, default=None: {
            "config.add_repo_metadata": True,
            "config.add_repo_metadata_file_list": ["AGENTS.MD"]
        }.get(key, default)
        monkeypatch.setattr('pr_agent.algo.repo_metadata.get_settings', lambda: settings_mock)
        
        # Act
        result = get_repo_metadata_content(git_provider)
        
        # Assert
        assert result == ""

    def test_pr_branch_exception(self, monkeypatch):
        """Test that empty string is returned when getting PR branch raises exception"""
        # Arrange
        git_provider = Mock()
        git_provider.get_pr_branch.side_effect = Exception("Test exception")
        
        settings_mock = Mock()
        settings_mock.get = lambda key, default=None: {
            "config.add_repo_metadata": True,
            "config.add_repo_metadata_file_list": ["AGENTS.MD"]
        }.get(key, default)
        monkeypatch.setattr('pr_agent.algo.repo_metadata.get_settings', lambda: settings_mock)
        
        # Act
        result = get_repo_metadata_content(git_provider)
        
        # Assert
        assert result == ""

    def test_single_file_success(self, monkeypatch):
        """Test successful reading of a single metadata file"""
        # Arrange
        git_provider = Mock()
        git_provider.get_pr_branch.return_value = "feature-branch"
        git_provider.get_pr_file_content = Mock(return_value="# Agent Guidelines\n\nFollow these rules...")
        
        settings_mock = Mock()
        settings_mock.get = lambda key, default=None: {
            "config.add_repo_metadata": True,
            "config.add_repo_metadata_file_list": ["AGENTS.MD"]
        }.get(key, default)
        monkeypatch.setattr('pr_agent.algo.repo_metadata.get_settings', lambda: settings_mock)
        
        # Act
        result = get_repo_metadata_content(git_provider)
        
        # Assert
        assert "Repository-Specific Rules and Guidelines" in result
        assert "AGENTS.MD" in result
        assert "Follow these rules..." in result
        assert git_provider.get_pr_file_content.called

    def test_multiple_files_success(self, monkeypatch):
        """Test successful reading of multiple metadata files"""
        # Arrange
        git_provider = Mock()
        git_provider.get_pr_branch.return_value = "feature-branch"
        
        def mock_get_file_content(file_path, branch):
            files = {
                "AGENTS.MD": "# Agent Guidelines",
                "docs/standards.md": "# Coding Standards",
                "security/compliance.md": "# Security Rules"
            }
            return files.get(file_path, "")
        
        git_provider.get_pr_file_content = Mock(side_effect=mock_get_file_content)
        
        settings_mock = Mock()
        settings_mock.get = lambda key, default=None: {
            "config.add_repo_metadata": True,
            "config.add_repo_metadata_file_list": ["AGENTS.MD", "docs/standards.md", "security/compliance.md"]
        }.get(key, default)
        monkeypatch.setattr('pr_agent.algo.repo_metadata.get_settings', lambda: settings_mock)
        
        # Act
        result = get_repo_metadata_content(git_provider)
        
        # Assert
        assert "AGENTS.MD" in result
        assert "docs/standards.md" in result
        assert "security/compliance.md" in result
        assert "Agent Guidelines" in result
        assert "Coding Standards" in result
        assert "Security Rules" in result
        assert result.count("### Repository Metadata File:") == 3

    def test_file_not_found(self, monkeypatch):
        """Test handling when a metadata file is not found"""
        # Arrange
        git_provider = Mock()
        git_provider.get_pr_branch.return_value = "feature-branch"
        git_provider.get_pr_file_content = Mock(return_value=None)
        
        settings_mock = Mock()
        settings_mock.get = lambda key, default=None: {
            "config.add_repo_metadata": True,
            "config.add_repo_metadata_file_list": ["NONEXISTENT.MD"]
        }.get(key, default)
        monkeypatch.setattr('pr_agent.algo.repo_metadata.get_settings', lambda: settings_mock)
        
        # Act
        result = get_repo_metadata_content(git_provider)
        
        # Assert
        assert result == ""

    def test_file_empty(self, monkeypatch):
        """Test handling when a metadata file is empty"""
        # Arrange
        git_provider = Mock()
        git_provider.get_pr_branch.return_value = "feature-branch"
        git_provider.get_pr_file_content = Mock(return_value="")
        
        settings_mock = Mock()
        settings_mock.get = lambda key, default=None: {
            "config.add_repo_metadata": True,
            "config.add_repo_metadata_file_list": ["EMPTY.MD"]
        }.get(key, default)
        monkeypatch.setattr('pr_agent.algo.repo_metadata.get_settings', lambda: settings_mock)
        
        # Act
        result = get_repo_metadata_content(git_provider)
        
        # Assert
        assert result == ""

    def test_mixed_success_and_failure(self, monkeypatch):
        """Test when some files are found and others are not"""
        # Arrange
        git_provider = Mock()
        git_provider.get_pr_branch.return_value = "feature-branch"
        
        def mock_get_file_content(file_path, branch):
            if file_path == "AGENTS.MD":
                return "# Agent Guidelines"
            elif file_path == "MISSING.MD":
                return None
            elif file_path == "docs/standards.md":
                return "# Coding Standards"
            return None
        
        git_provider.get_pr_file_content = Mock(side_effect=mock_get_file_content)
        
        settings_mock = Mock()
        settings_mock.get = lambda key, default=None: {
            "config.add_repo_metadata": True,
            "config.add_repo_metadata_file_list": ["AGENTS.MD", "MISSING.MD", "docs/standards.md"]
        }.get(key, default)
        monkeypatch.setattr('pr_agent.algo.repo_metadata.get_settings', lambda: settings_mock)
        
        # Act
        result = get_repo_metadata_content(git_provider)
        
        # Assert
        assert "AGENTS.MD" in result
        assert "docs/standards.md" in result
        assert "MISSING.MD" not in result
        assert "Agent Guidelines" in result
        assert "Coding Standards" in result

    def test_file_with_leading_slash(self, monkeypatch):
        """Test that leading slashes are properly stripped from file paths"""
        # Arrange
        git_provider = Mock()
        git_provider.get_pr_branch.return_value = "feature-branch"
        git_provider.get_pr_file_content = Mock(return_value="# Content")
        
        settings_mock = Mock()
        settings_mock.get = lambda key, default=None: {
            "config.add_repo_metadata": True,
            "config.add_repo_metadata_file_list": ["/AGENTS.MD"]
        }.get(key, default)
        monkeypatch.setattr('pr_agent.algo.repo_metadata.get_settings', lambda: settings_mock)
        
        # Act
        result = get_repo_metadata_content(git_provider)
        
        # Assert
        # Verify that get_pr_file_content was called with the normalized path (without leading slash)
        git_provider.get_pr_file_content.assert_called_with("AGENTS.MD", "feature-branch")
        assert "AGENTS.MD" in result

    def test_exception_reading_file(self, monkeypatch):
        """Test handling when reading a file raises an exception"""
        # Arrange
        git_provider = Mock()
        git_provider.get_pr_branch.return_value = "feature-branch"
        git_provider.get_pr_file_content = Mock(side_effect=Exception("Read error"))
        
        settings_mock = Mock()
        settings_mock.get = lambda key, default=None: {
            "config.add_repo_metadata": True,
            "config.add_repo_metadata_file_list": ["AGENTS.MD"]
        }.get(key, default)
        monkeypatch.setattr('pr_agent.algo.repo_metadata.get_settings', lambda: settings_mock)
        
        # Act
        result = get_repo_metadata_content(git_provider)
        
        # Assert
        assert result == ""

    def test_fallback_to_alternative_method(self, monkeypatch):
        """Test fallback to alternative method when get_pr_file_content is not available"""
        # Arrange
        git_provider = Mock(spec=[])  # Mock without get_pr_file_content method
        git_provider.get_pr_branch = Mock(return_value="feature-branch")
        
        settings_mock = Mock()
        settings_mock.get = lambda key, default=None: {
            "config.add_repo_metadata": True,
            "config.add_repo_metadata_file_list": ["AGENTS.MD"]
        }.get(key, default)
        monkeypatch.setattr('pr_agent.algo.repo_metadata.get_settings', lambda: settings_mock)
        
        # Mock the alternative method
        with patch('pr_agent.algo.repo_metadata._read_metadata_file_alternative', return_value="# Fallback content"):
            # Act
            result = get_repo_metadata_content(git_provider)
            
            # Assert
            assert "Fallback content" in result

    def test_header_format(self, monkeypatch):
        """Test that the header is properly formatted"""
        # Arrange
        git_provider = Mock()
        git_provider.get_pr_branch.return_value = "feature-branch"
        git_provider.get_pr_file_content = Mock(return_value="# Content")
        
        settings_mock = Mock()
        settings_mock.get = lambda key, default=None: {
            "config.add_repo_metadata": True,
            "config.add_repo_metadata_file_list": ["AGENTS.MD"]
        }.get(key, default)
        monkeypatch.setattr('pr_agent.algo.repo_metadata.get_settings', lambda: settings_mock)
        
        # Act
        result = get_repo_metadata_content(git_provider)
        
        # Assert
        assert result.startswith("## 📋 Repository-Specific Rules and Guidelines")
        assert "coding standards" in result.lower()
        assert "security guidelines" in result.lower()
        assert "best practices" in result.lower()

    def test_whitespace_handling(self, monkeypatch):
        """Test that whitespace in file paths is properly handled"""
        # Arrange
        git_provider = Mock()
        git_provider.get_pr_branch.return_value = "feature-branch"
        git_provider.get_pr_file_content = Mock(return_value="# Content")
        
        settings_mock = Mock()
        settings_mock.get = lambda key, default=None: {
            "config.add_repo_metadata": True,
            "config.add_repo_metadata_file_list": ["  AGENTS.MD  ", ""]
        }.get(key, default)
        monkeypatch.setattr('pr_agent.algo.repo_metadata.get_settings', lambda: settings_mock)
        
        # Act
        result = get_repo_metadata_content(git_provider)
        
        # Assert
        git_provider.get_pr_file_content.assert_called_once_with("AGENTS.MD", "feature-branch")

    def test_content_formatting(self, monkeypatch):
        """Test that content is properly formatted with separators"""
        # Arrange
        git_provider = Mock()
        git_provider.get_pr_branch.return_value = "feature-branch"
        
        def mock_get_file_content(file_path, branch):
            return f"Content from {file_path}"
        
        git_provider.get_pr_file_content = Mock(side_effect=mock_get_file_content)
        
        settings_mock = Mock()
        settings_mock.get = lambda key, default=None: {
            "config.add_repo_metadata": True,
            "config.add_repo_metadata_file_list": ["FILE1.MD", "FILE2.MD"]
        }.get(key, default)
        monkeypatch.setattr('pr_agent.algo.repo_metadata.get_settings', lambda: settings_mock)
        
        # Act
        result = get_repo_metadata_content(git_provider)
        
        # Assert
        assert "### Repository Metadata File: `FILE1.MD`" in result
        assert "### Repository Metadata File: `FILE2.MD`" in result
        assert "---" in result  # Separator between files


class TestReadMetadataFileAlternative:
    """Test cases for _read_metadata_file_alternative function"""

    @patch('tempfile.TemporaryDirectory')
    def test_successful_file_read(self, mock_temp_dir, monkeypatch):
        """Test successful file reading using alternative method"""
        # Arrange
        git_provider = Mock()
        git_provider.get_git_repo_url = Mock(return_value="https://github.com/test/repo.git")
        git_provider.get_pr_url = Mock(return_value="https://github.com/test/repo/pull/1")
        
        mock_repo = Mock()
        mock_repo.path = "/tmp/repo"
        git_provider.clone = Mock(return_value=mock_repo)
        
        mock_temp_dir_instance = MagicMock()
        mock_temp_dir_instance.__enter__.return_value = "/tmp/test"
        mock_temp_dir.return_value = mock_temp_dir_instance
        
        # Mock file reading
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = "# File content"
            
            with patch('os.path.exists', return_value=True):
                with patch('os.path.isfile', return_value=True):
                    # Act
                    result = _read_metadata_file_alternative(git_provider, "AGENTS.MD", "main")
                    
                    # Assert
                    assert result == "# File content"

    def test_file_not_found_alternative(self, monkeypatch):
        """Test alternative method when file doesn't exist"""
        # Arrange
        git_provider = Mock()
        git_provider.get_git_repo_url = Mock(return_value="https://github.com/test/repo.git")
        git_provider.get_pr_url = Mock(return_value="https://github.com/test/repo/pull/1")
        
        mock_repo = Mock()
        mock_repo.path = "/tmp/repo"
        git_provider.clone = Mock(return_value=mock_repo)
        
        with patch('tempfile.TemporaryDirectory'):
            with patch('os.path.exists', return_value=False):
                # Act
                result = _read_metadata_file_alternative(git_provider, "MISSING.MD", "main")
                
                # Assert
                assert result == ""

    def test_exception_in_alternative_method(self, monkeypatch):
        """Test exception handling in alternative method"""
        # Arrange
        git_provider = Mock()
        git_provider.get_git_repo_url = Mock(side_effect=Exception("Clone error"))
        git_provider.get_pr_url = Mock(return_value="https://github.com/test/repo/pull/1")
        
        # Act
        result = _read_metadata_file_alternative(git_provider, "AGENTS.MD", "main")
        
        # Assert
        assert result == ""

    def test_no_repo_url(self, monkeypatch):
        """Test alternative method when repo URL is not available"""
        # Arrange
        git_provider = Mock()
        git_provider.get_git_repo_url = Mock(return_value=None)
        git_provider.get_pr_url = Mock(return_value="https://github.com/test/repo/pull/1")
        
        # Act
        result = _read_metadata_file_alternative(git_provider, "AGENTS.MD", "main")
        
        # Assert
        assert result == ""

    def test_clone_failure(self, monkeypatch):
        """Test alternative method when cloning fails"""
        # Arrange
        git_provider = Mock()
        git_provider.get_git_repo_url = Mock(return_value="https://github.com/test/repo.git")
        git_provider.get_pr_url = Mock(return_value="https://github.com/test/repo/pull/1")
        git_provider.clone = Mock(return_value=None)
        
        with patch('tempfile.TemporaryDirectory'):
            # Act
            result = _read_metadata_file_alternative(git_provider, "AGENTS.MD", "main")
            
            # Assert
            assert result == ""

