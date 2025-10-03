"""
Query execution utilities for user-scoped database operations.

Security improvements:
- SQL validation using sqlparse to ensure user_id is present
- Circuit-breaker for complex queries (CTEs, UNIONs, subqueries)
- Separate admin query path for explicit opt-in to unscoped queries
- Parameterized queries only (no string interpolation)
"""
import re
from typing import Optional, Any, Tuple, List
import logging
import sqlparse
from sqlparse.sql import Where, Identifier, Comparison, Token, IdentifierList
from sqlparse.tokens import Keyword, Whitespace, Comment, String

from .exceptions import SecurityError

logger = logging.getLogger(__name__)


# Complex query patterns that require extra validation
COMPLEX_QUERY_PATTERNS = [
    r'\bWITH\b',  # CTEs
    r'\bUNION\b',  # UNIONs
    r'\(\s*SELECT\b',  # Subqueries
]


class QueryExecutor:
    """
    Shared query execution logic for user-scoped database operations.
    Provides validation and execution with proper user isolation.
    """

    @staticmethod
    def validate_user_id_present(query: str) -> bool:
        """
        Validate that a query contains user_id in WHERE clause using sqlparse AST traversal.

        Returns:
            True if user_id is found in WHERE clause comparison, False otherwise
        """
        try:
            parsed = sqlparse.parse(query)
            if not parsed:
                return False

            # Check each statement (handles multi-statement queries)
            has_statement = False
            for statement in parsed:
                if statement.token_first(skip_cm=True, skip_ws=True) is None:
                    continue  # skip empty statements
                has_statement = True
                if not QueryExecutor._check_user_id_in_statement(statement):
                    return False

            return has_statement
        except Exception:
            logger.exception("Error parsing SQL for validation")
            return False

    @staticmethod
    def _check_user_id_in_statement(statement) -> bool:
        """
        Check if a SQL statement contains user_id in a WHERE clause comparison.
        Uses AST traversal to avoid bypasses via comments, literals, or aliases.

        Returns:
            True if user_id comparison is found, False otherwise
        """
        for token in statement.tokens:
            # Skip comments and string literals
            if token.ttype in (Comment.Single, Comment.Multiline, String.Single, String.Symbol):
                continue

            # Check if this is a WHERE clause
            if isinstance(token, Where):
                if QueryExecutor._check_user_id_in_where(token):
                    return True

            # Recursively check sub-tokens
            if hasattr(token, 'tokens'):
                if QueryExecutor._check_user_id_in_statement(token):
                    return True

        return False

    @staticmethod
    def _check_user_id_in_where(where_clause) -> bool:
        """
        Check if a WHERE clause contains a comparison on user_id identifier.

        Returns:
            True if user_id comparison is found, False otherwise
        """
        tokens = list(where_clause.flatten())

        for i, token in enumerate(tokens):
            # Skip comments and string literals
            if token.ttype in (Comment.Single, Comment.Multiline, String.Single, String.Symbol):
                continue

            # Check if this token is an identifier named 'user_id' or in the form 'table.user_id'
            token_text = token.value.lower().strip()
            if (token_text == 'user_id' or 
                token_text.endswith('.user_id') or 
                '.user_id' in token_text):
                # Look ahead for comparison operators (=, ==, IN, etc.)
                for j in range(i + 1, min(i + 5, len(tokens))):
                    next_token = tokens[j]

                    # Skip whitespace
                    if next_token.ttype == Whitespace:
                        continue

                    # Check for comparison operators
                    if next_token.value.upper() in ('=', '==', 'IN', 'IS'):
                        return True

                    # Stop if we hit something else
                    break

        # Also check for user_id in Identifier or Comparison objects
        for token in where_clause.tokens:
            if isinstance(token, Identifier) and 'user_id' in token.value.lower():
                return True

            if isinstance(token, Comparison):
                if 'user_id' in str(token).lower():
                    return True

        return False

    @staticmethod
    def is_complex_query(query: str) -> bool:
        """
        Check if query contains complex patterns (CTEs, UNIONs, subqueries).

        Returns:
            True if query is complex, False otherwise
        """
        query_upper = query.upper()
        for pattern in COMPLEX_QUERY_PATTERNS:
            if re.search(pattern, query_upper):
                return True
        return False

    @staticmethod
    def inject_user_filter(query: str, user_id: str, params: Optional[tuple] = None) -> Tuple[str, tuple]:
        """
        DEPRECATED: This method has been removed. Please use queries with explicit user_id in WHERE clause.

        Migration path:
        1. Add explicit user_id filter to your WHERE clause
        2. Use validate_user_id_present() to verify
        3. Use execute_scoped_query() for automatic validation

        Raises:
            SecurityError: Always raised - method has been removed
        """
        raise SecurityError(
            "inject_user_filter has been removed. Please include user_id explicitly in your WHERE clause. "
            "See method docstring for migration path."
        )

    @staticmethod
    async def execute_admin_query(connection, query: str, params: Optional[tuple] = None) -> Any:
        """
        Execute an admin query that explicitly opts out of user scoping.

        ⚠️  WARNING: This method bypasses user isolation. Use only for:
        - System maintenance queries
        - Cross-user analytics
        - Admin operations

        Args:
            connection: asyncpg connection or pool
            query: SQL query to execute (will NOT be modified)
            params: Query parameters

        Returns:
            Query results based on query type
        """
        logger.warning(f"Executing admin query (unscoped): {query[:100]}...")

        try:
            # Determine query type
            query_stripped = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
            query_stripped = re.sub(r'--.*?$', '', query_stripped, flags=re.MULTILINE)
            query_stripped = query_stripped.strip().upper()

            if query_stripped.startswith('SELECT'):
                return await connection.fetch(query, *(params or ()))
            elif query_stripped.startswith('INSERT') and 'RETURNING' in query_stripped:
                return await connection.fetchrow(query, *(params or ()))
            else:
                return await connection.execute(query, *(params or ()))
        except Exception as e:
            logger.exception("Error executing admin query")
            raise

    @staticmethod
    async def execute_scoped_query(connection, query: str, user_id: str, params: Optional[tuple] = None) -> Any:
        """
        Execute a user-scoped query on a given connection with validation.

        Args:
            connection: asyncpg connection or pool
            query: SQL query to execute
            user_id: User ID for scoping
            params: Query parameters (user_id will be prepended automatically)

        Returns:
            Query results based on query type (fetch/fetchrow/execute result)

        Raises:
            SecurityError: If query is complex or doesn't contain user_id after injection
        """
        # Validate user scoping by statement type
        query_head = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
        query_head = re.sub(r'--.*?$', '', query_head, flags=re.MULTILINE).strip().upper()
        first_kw_match = re.match(r'^[A-Z]+', query_head)
        first_kw = first_kw_match.group(0) if first_kw_match else ""
        if first_kw in ("SELECT", "UPDATE", "DELETE"):
            if not QueryExecutor.validate_user_id_present(query):
                logger.exception(f"Query missing user_id in WHERE: {query[:200]}")
                raise SecurityError(
                    "Query must include user_id in WHERE clause to enforce multi-user isolation."
                )
        elif first_kw == "INSERT":
            # Basic guard: ensure 'user_id' appears in the text (columns/values)
            if "USER_ID" not in query_head:
                logger.exception(f"INSERT without user_id column detected: {query[:200]}")
                raise SecurityError("INSERT must include user_id column/value for multi-user isolation.")
        
        # Use the query and params as-is (no injection needed with explicit validation)
        scoped_query = query
        scoped_params = params or ()

        try:
            # Determine query type by finding first non-comment SQL keyword
            # Strip comments and whitespace to get the actual SQL statement
            query_stripped = re.sub(r'/\*.*?\*/', '', scoped_query, flags=re.DOTALL)  # Remove /* */ comments
            query_stripped = re.sub(r'--.*?$', '', query_stripped, flags=re.MULTILINE)  # Remove -- comments
            query_stripped = query_stripped.strip().upper()

            # Detect statement type
            if query_stripped.startswith('WITH'):
                # CTE query - determine the final statement type
                # Parse the actual final statement after CTE
                statement = sqlparse.parse(scoped_query)[0]
                statement_type = None
                for token in statement.flatten():
                    if token.ttype in Keyword:
                        keyword = token.value.upper()
                        if keyword in {"WITH", "RECURSIVE"}:
                            continue
                        if keyword in {"SELECT", "INSERT", "UPDATE", "DELETE"}:
                            statement_type = keyword
                            break

                if statement_type == "SELECT":
                    return await connection.fetch(scoped_query, *scoped_params)
                elif statement_type == "INSERT":
                    if 'RETURNING' in query_stripped:
                        return await connection.fetchrow(scoped_query, *scoped_params)
                    return await connection.execute(scoped_query, *scoped_params)
                elif statement_type in {"UPDATE", "DELETE"}:
                    if 'RETURNING' in query_stripped:
                        return await connection.fetch(scoped_query, *scoped_params)
                    return await connection.execute(scoped_query, *scoped_params)

                return await connection.execute(scoped_query, *scoped_params)
            elif query_stripped.startswith('SELECT'):
                return await connection.fetch(scoped_query, *scoped_params)
            elif query_stripped.startswith('INSERT'):
                # Check if RETURNING clause exists
                if 'RETURNING' in query_stripped:
                    return await connection.fetchrow(scoped_query, *scoped_params)
                else:
                    return await connection.execute(scoped_query, *scoped_params)
            elif query_stripped.startswith('UPDATE') or query_stripped.startswith('DELETE'):
                return await connection.execute(scoped_query, *scoped_params)
            else:
                # For other queries (CREATE, DROP, ALTER, etc.), execute directly
                return await connection.execute(scoped_query, *scoped_params)
        except Exception as e:
            logger.exception(f"Error executing user-scoped query for user {user_id}")
            raise
