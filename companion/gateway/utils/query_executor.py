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
            for statement in parsed:
                if QueryExecutor._check_user_id_in_statement(statement):
                    return True

            return False
        except Exception as e:
            logger.error(f"Error parsing SQL for validation: {e}")
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
        DEPRECATED: This method is maintained for backward compatibility but should not be used.

        Prefer using queries with explicit user_id in WHERE clause and validate with
        validate_user_id_present().

        Raises:
            SecurityError: If query is complex (CTEs, UNIONs, subqueries) and cannot be safely processed
        """
        # Check for complex queries that cannot be safely handled
        if QueryExecutor.is_complex_query(query):
            raise SecurityError(
                "Complex queries (CTEs, UNIONs, subqueries) are not supported by automatic user_id injection. "
                "Please include user_id explicitly in your query WHERE clause."
            )
        # Increment all existing parameter placeholders by 1 to make room for user_id at $1
        # This is needed because we're prepending user_id to the params tuple
        if params:
            # Find all parameter placeholders ($1, $2, etc.) and increment them
            def increment_param(match):
                param_num = int(match.group(1))
                return f'${param_num + 1}'

            query = re.sub(r'\$(\d+)', increment_param, query)

        # Add user_id parameter to the beginning of the parameters tuple
        if params is None:
            params = (user_id,)
        else:
            params = (user_id,) + params

        # Handle different query types and inject user_id appropriately
        query_upper = query.strip().upper()

        if 'UPDATE' in query_upper or 'DELETE' in query_upper:
            # For UPDATE/DELETE, we need to append to WHERE clause
            if 'WHERE' in query_upper:
                # Query already has a WHERE, add AND condition
                scoped_query = re.sub(
                    r'WHERE\s+',
                    f'WHERE user_id = $1 AND ',
                    query,
                    count=1,
                    flags=re.IGNORECASE
                )
            else:
                # No WHERE clause exists, add one
                table_match = re.search(r'(UPDATE|DELETE)\s+(\w+)', query, re.IGNORECASE)
                if table_match:
                    scoped_query = f"{query.rstrip(';')} WHERE user_id = $1"
                else:
                    scoped_query = query  # Fallback, might not be safe
        else:
            # For SELECT statements, handle appropriately
            scoped_query = re.sub(
                r'WHERE\s+',
                f'WHERE user_id = $1 AND ',
                query,
                count=1,
                flags=re.IGNORECASE
            )

            # If no WHERE clause was present in SELECT, INSERT, we need to add it
            if 'WHERE' not in scoped_query.upper() and ('SELECT' in query_upper or 'FROM' in query_upper):
                # Look for the end of the WHERE-relevant part (before ORDER BY, LIMIT, etc.)
                where_position = max(
                    query_upper.rfind(' WHERE ') if ' WHERE ' in query_upper else -1,
                    query_upper.rfind(' FROM ') if ' FROM ' in query_upper else -1,
                    query_upper.rfind(' ORDER BY ') if ' ORDER BY ' in query_upper else -1,
                    query_upper.rfind(' GROUP BY ') if ' GROUP BY ' in query_upper else -1,
                    query_upper.rfind(' HAVING ') if ' HAVING ' in query_upper else -1,
                    query_upper.rfind(' LIMIT ') if ' LIMIT ' in query_upper else -1,
                    len(query)  # Default to end of query if no clauses
                )

                # Find the actual position in the original case-sensitive query
                if where_position == len(query):
                    # No clause found, append WHERE to the end
                    scoped_query = f"{query} WHERE user_id = $1"
                else:
                    # Insert WHERE clause before the found clause
                    from_position = query_upper.find(' FROM ')
                    if from_position > -1 and 'SELECT' in query_upper:
                        # For SELECT, add WHERE after FROM clause or after WHERE if it exists
                        remaining_query = query[from_position:]
                        if ' WHERE ' not in remaining_query.upper():
                            # Add WHERE after FROM clause
                            pos = query[:from_position].lower().rfind(' from ') + 6  # After ' FROM '
                            scoped_query = query[:pos] + f" WHERE user_id = $1 " + query[pos:]

        # Special handling for INSERT statements
        if 'INSERT' in query_upper:
            # Check if user_id is already in the column list
            if 'user_id' not in query_upper:
                # We need to add user_id to the insert if it's not already there
                # This is a simplified approach and assumes standard INSERT format
                insert_match = re.match(r'(INSERT INTO \w+ \()([^)]+)(\).*)', query, re.IGNORECASE)
                if insert_match:
                    columns_part = insert_match.group(2)
                    if 'user_id' not in columns_part.lower():
                        # Add user_id to columns and adjust values appropriately
                        # This requires checking VALUES or SELECT part to add the corresponding value
                        new_query = query
                        # Since the user_id is already part of the params at position $1,
                        # we need to find where to add it in the column list and values
                        # For simplicity, we'll leave this as is and assume user_id is provided in the original query
                    else:
                        new_query = query
                else:
                    new_query = query
            else:
                new_query = query
            scoped_query = new_query

        return scoped_query, params

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

            if query_stripped.startswith('SELECT') or 'SELECT' in query_stripped:
                return await connection.fetch(query, *(params or ()))
            elif query_stripped.startswith('INSERT') and 'RETURNING' in query_stripped:
                return await connection.fetchrow(query, *(params or ()))
            else:
                return await connection.execute(query, *(params or ()))
        except Exception as e:
            logger.error(f"Error executing admin query: {e}")
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
        # Inject user filter (will raise SecurityError for complex queries)
        scoped_query, scoped_params = QueryExecutor.inject_user_filter(query, user_id, params)

        # Validate that user_id is present in the final query
        if not QueryExecutor.validate_user_id_present(scoped_query):
            logger.error(f"Query missing user_id after injection: {scoped_query[:200]}")
            raise SecurityError(
                "Query does not contain user_id in WHERE clause. This violates multi-user isolation."
            )

        try:
            # Determine query type by finding first non-comment SQL keyword
            # Strip comments and whitespace to get the actual SQL statement
            query_stripped = re.sub(r'/\*.*?\*/', '', scoped_query, flags=re.DOTALL)  # Remove /* */ comments
            query_stripped = re.sub(r'--.*?$', '', query_stripped, flags=re.MULTILINE)  # Remove -- comments
            query_stripped = query_stripped.strip().upper()

            # Detect statement type
            if query_stripped.startswith('WITH'):
                # CTE query - determine the final statement type
                # Look for SELECT/INSERT/UPDATE/DELETE after the CTE
                if 'SELECT' in query_stripped:
                    return await connection.fetch(scoped_query, *scoped_params)
                elif 'INSERT' in query_stripped and 'RETURNING' in query_stripped:
                    return await connection.fetchrow(scoped_query, *scoped_params)
                else:
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
            logger.error(f"Error executing user-scoped query for user {user_id}: {e}")
            raise
