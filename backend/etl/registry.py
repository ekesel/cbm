# etl/registry.py
from typing import Optional, Type
from metrics.models import Source, Board
from .connectors.jira import JiraConnector
from .connectors.clickup import ClickUpConnector
from .connectors.azure import AzureConnector
from .normalizers.jira import JiraNormalizer
from .normalizers.clickup import ClickUpNormalizer
from .normalizers.azure import AzureNormalizer
from .normalizers.github import GitHubPRNormalizer

def get_connector(board: Board):
    if board.source == Source.JIRA:
        return JiraConnector(board)
    if board.source == Source.CLICKUP:
        return ClickUpConnector(board)
    if board.source == Source.AZURE:
        return AzureConnector(board)
    raise NotImplementedError(f"No connector implemented for source={board.source}")

def get_normalizer(board: Board):
    if board.source == Source.JIRA:
        return JiraNormalizer(board)
    if board.source == Source.CLICKUP:
        return ClickUpNormalizer(board)
    if board.source == Source.AZURE:
        return AzureNormalizer(board)
    if board.source == Source.GITHUB:
        return GitHubPRNormalizer(board)
    raise NotImplementedError(f"No normalizer implemented for source={board.source}")