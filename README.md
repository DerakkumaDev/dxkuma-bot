<div align="center">

<img src="docs/dxkuma.png" width="20%">

# 迪拉熊Bot - Derakkuma Bot

一个更好玩更可维护的 音游/日常 Bot。

</div>

![Static Badge](https://img.shields.io/badge/Ver-KM25.39--A-blue)
![Static Badge](https://img.shields.io/badge/License-AGPLv3-orange)
![Static Badge](https://img.shields.io/badge/CPython-3.12%2B-green)
[![qq](https://img.shields.io/badge/2689340931-gray?logo=qq&style=social)](https://qm.qq.com/cgi-bin/qm/qr?k=LyQOTRI7ViXYSTg0zbS2sGgcmkbYrxbP)

## 任务板

| 任务        | 完成状态 |
|-----------|------|
| README.md | ✔️   |

## 介绍

迪拉熊Bot是一个主要面向舞萌DX玩家群体的IM Bot，在基础的群聊Bot功能之上追加了模块化的各类游戏功能支持。

迪拉熊Bot基于NoneBot2框架和OneBot v11协议，可以通过非常愉快的方式快速进行本地部署。

## 快速部署

```shell
git clone xxx.git derakkuma-bot

cd derakkuma-bot

uv sync

uv run start.py
```

## 依赖列表

| 依赖包名称            | 依赖版本   | 备注       |
|------------------|--------|----------|
| NoneBot2         | 2.4.3 | Bot 框架    |
| Volcengine SDK   | 4.0.21 | 火山引擎 SDK |
| PIL              | 11.3.0 | 图像处理库    |
| python-soundfile | 0.13.1 | 音频处理库    |
| Pykakasi         | 2.3.0 | 假名及罗马字转换  |
| RapidFuzz        | 3.14.1 | 模糊匹配库    |
| SQLAlchemy       | 2.0.43 | 对象关系映射器  |

## 制作&鸣谢

方长，Ekzykes