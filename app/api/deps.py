"""Common dependencies for API routes."""

from agents import root_agent


async def get_agent():
    """Get the root agent instance."""
    # Nếu sau này bạn muốn multi-tenant, có thể tạo agent khác nhau ở đây
    return root_agent
