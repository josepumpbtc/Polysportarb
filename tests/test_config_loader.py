# 目的：验证配置加载逻辑，默认值与 YAML 合并正确
# 方法：无文件时返回 DEFAULTS；有 YAML 时合并覆盖

import os
import tempfile
import pytest
from src.config_loader import load_config, DEFAULTS


def test_load_config_no_file_returns_defaults():
    """
    目的：无配置文件时返回默认配置，保证程序可运行
    预期：load_config 返回的字典包含 min_profit、fee_bps 等且值与 DEFAULTS 一致
    """
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "nonexistent.yaml")
        config = load_config(config_path=path)
        assert config["min_profit"] == DEFAULTS["min_profit"]
        assert config["fee_bps"] == DEFAULTS["fee_bps"]
        assert "sports_tag_id" in config


def test_load_config_with_yaml_merges():
    """
    目的：存在 YAML 时合并进默认配置，只覆盖提供的键
    预期：min_profit 被文件值覆盖，未在文件中出现的键保持默认
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("min_profit: 0.01\nfee_bps: 10\n")
        f.flush()
        path = f.name
    try:
        config = load_config(config_path=path)
        assert config["min_profit"] == 0.01
        assert config["fee_bps"] == 10
        assert config["events_limit"] == DEFAULTS["events_limit"]
    finally:
        os.unlink(path)
