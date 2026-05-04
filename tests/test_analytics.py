import pytest
from app import app
from flask import session

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_analytics_redirects_unauthenticated(client):
    """Test that /analytics redirects to /login for logged-out users."""
    response = client.get('/analytics', follow_redirects=False)
    assert response.status_code == 302
    assert '/login' in response.location

def test_analytics_accessible_authenticated(client):
    """Test that /analytics is accessible for logged-in users."""
    with client.session_transaction() as sess:
        sess['user_id'] = 1  # Mock logged-in user
    
    response = client.get('/analytics')
    assert response.status_code == 200
    assert b"Advanced Analytics" in response.data
    assert b"COMING SOON" in response.data

def test_navbar_shows_analytics_authenticated(client):
    """Test that the navbar shows 'Analytics' link only when authenticated."""
    # Unauthenticated
    response = client.get('/')
    assert b'href="/analytics"' not in response.data
    
    # Authenticated
    with client.session_transaction() as sess:
        sess['user_id'] = 1
    response = client.get('/')
    assert b'href="/analytics"' in response.data

def test_analytics_active_state(client):
    """Test that the Analytics link has the 'active' class when on the analytics page."""
    with client.session_transaction() as sess:
        sess['user_id'] = 1
    
    response = client.get('/analytics')
    assert b'class="nav-link active">Analytics</a>' in response.data
