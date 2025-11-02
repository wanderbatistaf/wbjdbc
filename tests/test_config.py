"""
Tests for configuration management.
"""

import os
import tempfile
import pytest
from wbjdbc.config import Config, get_config, reset_config


def test_default_config():
    """Test default configuration values."""
    config = Config()

    assert config.get('POOL_SIZE') == 10
    assert config.get('POOL_MAX_SIZE') == 20
    assert config.get('BATCH_SIZE') == 1000
    assert config.get('CACHE_ENABLED') is True
    assert config.get('ASYNC_ENABLED') is True


def test_env_file_loading():
    """Test loading configuration from .env file."""
    # Create temporary .env file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("WBJDBC_POOL_SIZE=25\n")
        f.write("WBJDBC_BATCH_SIZE=2000\n")
        f.write("WBJDBC_CACHE_ENABLED=false\n")
        env_file = f.name

    try:
        config = Config(env_file)
        assert config.get('POOL_SIZE') == 25
        assert config.get('BATCH_SIZE') == 2000
        assert config.get('CACHE_ENABLED') is False
    finally:
        os.unlink(env_file)


def test_get_pool_config():
    """Test pool configuration getter."""
    config = Config()
    pool_config = config.get_pool_config()

    assert 'pool_size' in pool_config
    assert 'max_size' in pool_config
    assert 'timeout' in pool_config
    assert pool_config['pool_size'] == 10


def test_get_cache_config():
    """Test cache configuration getter."""
    config = Config()
    cache_config = config.get_cache_config()

    assert 'enabled' in cache_config
    assert 'ttl' in cache_config
    assert 'max_size' in cache_config
    assert cache_config['enabled'] is True


def test_global_config():
    """Test global configuration instance."""
    reset_config()

    config1 = get_config()
    config2 = get_config()

    # Should return same instance
    assert config1 is config2


def test_config_set_get():
    """Test setting and getting custom config values."""
    config = Config()

    config.set('CUSTOM_KEY', 'custom_value')
    assert config.get('CUSTOM_KEY') == 'custom_value'

    # Non-existent key returns default
    assert config.get('NON_EXISTENT', 'default') == 'default'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
