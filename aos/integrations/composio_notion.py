"""
Composio Notion Integration for AOS

Wrapper around composio CLI for Notion operations.
Composio handles OAuth token refresh automatically.
"""

import json
import subprocess
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ComposioResult:
    """Result from a Composio tool execution."""
    successful: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    log_id: str


class ComposioNotionClient:
    """
    Client for Notion operations via Composio CLI.
    
    Composio maintains OAuth tokens and handles refresh automatically.
    No need to manage NOTION_API_KEY or token expiry.
    
    Available tools:
    - NOTION_SEARCH_NOTION_PAGE
    - NOTION_CREATE_NOTION_PAGE
    - NOTION_FETCH_BLOCK_CONTENTS
    - NOTION_FETCH_DATABASE
    - NOTION_FETCH_DATA
    - NOTION_QUERY_DATABASE_WITH_FILTER
    - NOTION_INSERT_ROW_DATABASE
    - NOTION_UPSERT_ROW_DATABASE
    - NOTION_APPEND_TEXT_BLOCKS
    - NOTION_APPEND_CODE_BLOCKS
    - NOTION_APPEND_TABLE_BLOCKS
    - NOTION_ADD_MULTIPLE_PAGE_CONTENT
    - NOTION_REPLACE_PAGE_CONTENT
    - NOTION_CREATE_DATABASE
    - NOTION_CREATE_VIEW
    - NOTION_LIST_VIEWS
    """
    
    def __init__(self):
        """Initialize client. Assumes 'composio' CLI is in PATH and notion is linked."""
        pass
    
    def _execute(self, tool_slug: str, data: Dict[str, Any]) -> ComposioResult:
        """
        Execute a Composio tool.
        
        Args:
            tool_slug: Tool name (e.g. "NOTION_SEARCH_NOTION_PAGE")
            data: Tool parameters as dict
            
        Returns:
            ComposioResult with successful/data/error/log_id
            
        Raises:
            RuntimeError: If composio CLI fails
        """
        cmd = ["composio", "execute", tool_slug, "-d", json.dumps(data)]
        
        result = None
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=True
            )
            
            response = json.loads(result.stdout)
            return ComposioResult(
                successful=response.get("successful", False),
                data=response.get("data"),
                error=response.get("error"),
                log_id=response.get("logId", "")
            )
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Composio CLI failed: {e.stderr}") from e
        except subprocess.TimeoutExpired:
            raise RuntimeError("Composio CLI timeout after 60s")
        except json.JSONDecodeError as e:
            stdout = result.stdout if result else "(no output)"
            raise RuntimeError(f"Invalid JSON from composio: {stdout}") from e
    
    def search_pages(
        self,
        query: str = "",
        page_size: int = 25,
        filter_value: str = "page",
        start_cursor: Optional[str] = None
    ) -> ComposioResult:
        """
        Search Notion pages.
        
        Args:
            query: Search query (empty = all pages)
            page_size: Results per page (max 100)
            filter_value: "page" or "database"
            start_cursor: Pagination cursor from previous result
            
        Returns:
            ComposioResult with results list, has_more, next_cursor
        """
        data = {
            "query": query,
            "page_size": page_size,
            "filter_value": filter_value,
            "filter_property": "object",
            "filter_properties": []
        }
        
        if start_cursor:
            data["start_cursor"] = start_cursor
        
        return self._execute("NOTION_SEARCH_NOTION_PAGE", data)
    
    def create_page(
        self,
        parent_id: str,
        title: str,
        markdown: Optional[str] = None,
        icon: Optional[str] = None,
        cover: Optional[str] = None
    ) -> ComposioResult:
        """
        Create a Notion page.
        
        Args:
            parent_id: Parent page or database ID (without dashes works)
            title: Page title
            markdown: Optional Notion-flavored markdown content
            icon: Optional single emoji
            cover: Optional cover image URL
            
        Returns:
            ComposioResult with created page data
        """
        data = {
            "parent_id": parent_id,
            "title": title
        }
        
        if markdown:
            data["markdown"] = markdown
        if icon:
            data["icon"] = icon
        if cover:
            data["cover"] = cover
        
        return self._execute("NOTION_CREATE_NOTION_PAGE", data)
    
    def fetch_page_content(self, page_id: str) -> ComposioResult:
        """
        Fetch page content as blocks.
        
        Args:
            page_id: Page ID
            
        Returns:
            ComposioResult with block list
        """
        return self._execute("NOTION_FETCH_BLOCK_CONTENTS", {"block_id": page_id})
    
    def fetch_database(self, database_id: str) -> ComposioResult:
        """
        Fetch database schema and properties.
        
        Args:
            database_id: Database ID
            
        Returns:
            ComposioResult with database metadata
        """
        return self._execute("NOTION_FETCH_DATABASE", {"database_id": database_id})
    
    def query_database(
        self,
        database_id: str,
        filter_obj: Optional[Dict[str, Any]] = None,
        sorts: Optional[List[Dict[str, str]]] = None,
        page_size: int = 100,
        start_cursor: Optional[str] = None
    ) -> ComposioResult:
        """
        Query a database with filters and sorts.
        
        Args:
            database_id: Database ID
            filter_obj: Notion filter object (property-based)
            sorts: List of sort specs [{"property": "Date", "direction": "descending"}]
            page_size: Results per page
            start_cursor: Pagination cursor
            
        Returns:
            ComposioResult with results list, has_more, next_cursor
        """
        data = {"database_id": database_id, "page_size": page_size}
        
        if filter_obj:
            data["filter"] = filter_obj
        if sorts:
            data["sorts"] = sorts
        if start_cursor:
            data["start_cursor"] = start_cursor
        
        return self._execute("NOTION_QUERY_DATABASE_WITH_FILTER", data)
    
    def insert_database_row(
        self,
        database_id: str,
        properties: Dict[str, Any]
    ) -> ComposioResult:
        """
        Insert a row into a database.
        
        Args:
            database_id: Database ID
            properties: Property values keyed by property name
            
        Returns:
            ComposioResult with created page
        """
        return self._execute("NOTION_INSERT_ROW_DATABASE", {
            "database_id": database_id,
            "properties": properties
        })
    
    def append_text_blocks(
        self,
        page_id: str,
        text_blocks: List[str]
    ) -> ComposioResult:
        """
        Append text blocks to a page.
        
        Args:
            page_id: Page ID
            text_blocks: List of text paragraphs
            
        Returns:
            ComposioResult
        """
        return self._execute("NOTION_APPEND_TEXT_BLOCKS", {
            "page_id": page_id,
            "text_blocks": text_blocks
        })
    
    def append_code_blocks(
        self,
        page_id: str,
        code_blocks: List[Dict[str, str]]
    ) -> ComposioResult:
        """
        Append code blocks to a page.
        
        Args:
            page_id: Page ID
            code_blocks: List of {"language": "python", "code": "..."}
            
        Returns:
            ComposioResult
        """
        return self._execute("NOTION_APPEND_CODE_BLOCKS", {
            "page_id": page_id,
            "code_blocks": code_blocks
        })


# Convenience functions for direct CLI usage from skills/scripts

def composio_notion_search(query: str = "", page_size: int = 10) -> Dict[str, Any]:
    """
    Quick search shortcut for skills.
    
    Returns raw data dict or raises RuntimeError.
    """
    client = ComposioNotionClient()
    result = client.search_pages(query=query, page_size=page_size)
    
    if not result.successful or result.data is None:
        raise RuntimeError(f"Notion search failed: {result.error}")
    
    return result.data


def composio_notion_create_page(
    parent_id: str,
    title: str,
    markdown: Optional[str] = None
) -> Dict[str, Any]:
    """
    Quick page creation shortcut for skills.
    
    Returns raw data dict or raises RuntimeError.
    """
    client = ComposioNotionClient()
    result = client.create_page(parent_id=parent_id, title=title, markdown=markdown)
    
    if not result.successful or result.data is None:
        raise RuntimeError(f"Notion page creation failed: {result.error}")
    
    return result.data
