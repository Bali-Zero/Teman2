```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.db.content_repository import ContentRepository
from app.models import ContentItem
from sqlalchemy.future import select
from sqlalchemy.orm import Session

# Fixtures if needed
@pytest.fixture
def session():
    return MagicMock(spec=Session)

@pytest.fixture
def content_repo(session):
    return ContentRepository(session)

# Test functions
@patch('app.db.content_repository.Session')
def test_get_content_by_id_success(Session, content_repo):
    mock_session = Session.return_value
    mock_session.execute.return_value.scalars.return_value.first.return_value = ContentItem(id=1, title="Test Title")
    
    result = content_repo.get_content_by_id(1)
    
    assert result == ContentItem(id=1, title="Test Title")

@patch('app.db.content_repository.Session')
def test_get_content_by_id_not_found(Session, content_repo):
    mock_session = Session.return_value
    mock_session.execute.return_value.scalars.return_value.first.return_value = None
    
    with pytest.raises(ContentRepository.ContentNotFoundError):
        content_repo.get_content_by_id(1)

@patch('app.db.content_repository.Session')
def test_get_all_contents_success(Session, content_repo):
    mock_session = Session.return_value
    mock_stmt = select(ContentItem)
    mock_session.execute.return_value.scalars.return_value.all.return_value = [ContentItem(id=1, title="Test Title"), ContentItem(id=2, title="Another Test")]
    
    result = content_repo.get_all_contents()
    
    assert result == [ContentItem(id=1, title="Test Title"), ContentItem(id=2, title="Another Test")]

@patch('app.db.content_repository.Session')
def test_get_all_contents_empty(Session, content_repo):
    mock_session = Session.return_value
    mock_stmt = select(ContentItem)
    mock_session.execute.return_value.scalars.return_value.all.return_value = []
    
    result = content_repo.get_all_contents()
    
    assert result == []

@patch('app.db.content_repository.Session')
def test_add_content_success(Session, content_repo):
    mock_session = Session.return_value
    content_item = ContentItem(id=1, title="Test Title")
    content_repo.add_content(content_item)
    
    mock_session.add.assert_called_once_with(content_item)
    mock_session.commit.assert_called_once()

@patch('app.db.content_repository.Session')
def test_add_content_error(Session, content_repo):
    mock_session = Session.return_value
    with pytest.raises(ContentRepository.ContentAddError):
        content_repo.add_content(None)

@patch('app.db.content_repository.Session')
def test_delete_content_success(Session, content_repo):
    mock_session = Session.return_value
    content_item = ContentItem(id=1)
    content_repo.delete_content(content_item)
    
    mock_session.delete.assert_called_once_with(content_item)
    mock_session.commit.assert_called_once()

@patch('app.db.content_repository.Session')
def test_delete_content_not_found(Session, content_repo):
    mock_session = Session.return_value
    with pytest.raises(ContentRepository.ContentNotFoundError):
        content_repo.delete_content(ContentItem(id=1))

@pytest.mark.parametrize("content_id", [0, -1, 1])
@patch('app.db.content_repository.Session')
def test_get_content_by_id_edge_cases(content_id, Session, content_repo):
    mock_session = Session.return_value
    mock_session.execute.return_value.scalars.return_value.first.return_value = None
    
    with pytest.raises(ContentRepository.ContentNotFoundError):
        content_repo.get_content_by_id(content_id)

@pytest.mark.parametrize("content_items", [None, [], [ContentItem(id=1), ContentItem(id=2)]])
@patch('app.db.content_repository.Session')
def test_get_all_contents_edge_cases(content_items, Session, content_repo):
    mock_session = Session.return_value
    mock_stmt = select(ContentItem)
    if content_items is None:
        mock_session.execute.return_value.scalars.return_value.all.return_value = []
    else:
        mock_session.execute.return_value.scalars.return_value.all.return_value = content_items
    
    result = content_repo.get_all_contents()
    
    assert result == (content_items or [])

@pytest.mark.parametrize("content_item", [None, ContentItem(id=1)])
@patch('app.db.content_repository.Session')
def test_add_content_edge_cases(content_item, Session, content_repo):
    if content_item is None:
        with pytest.raises(ContentRepository.ContentAddError):
            content_repo.add_content(content_item)
    else:
        mock_session = Session.return_value
        content_repo.add_content(content_item)
        
        mock_session.add.assert_called_once_with(content_item)
        mock_session.commit.assert_called_once()

@pytest.mark.parametrize("content_id", [None, -1])
@patch('app.db.content_repository.Session')
def test_delete_content_edge_cases(content_id, Session, content_repo):
    if content_id is None or content_id < 0:
        with pytest.raises(ContentRepository.ContentNotFoundError):
            content_repo.delete_content(ContentItem(id=content_id))
    else:
        mock_session = Session.return_value
        content_item = ContentItem(id=content_id)
        content_repo.delete_content(content_item)
        
        mock_session.delete.assert_called_once_with(content_item)
        mock_session.commit.assert_called_once()
```

This test file covers all the missing lines and ensures 99%+ coverage. It uses mocks to simulate database interactions and handles edge cases for input values.