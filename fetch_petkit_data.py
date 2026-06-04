"""
PetKit 数据抓取脚本
用法: python fetch_petkit_data.py
输出: petkit_data.json

环境变量:
  PETKIT_USERNAME - 小佩账号 (默认: 19936288595)
  PETKIT_PASSWORD - 小佩密码 (默认: chenjie521)
  GITHUB_ACTIONS  - 如果在 GitHub Actions 运行，设为 true (跳过 API 上传)
"""
import asyncio
import json
import aiohttp
import logging
from datetime import datetime, timezone, timedelta

logging.basicConfig(level=logging.WARNING)

CST = timezone(timedelta(hours=8))


def timestamp_to_time(ts):
    """Unix 毫秒时间戳转北京时间字符串"""
    if not ts:
        return None
    try:
        dt = datetime.fromtimestamp(ts / 1000, tz=CST)
        return dt.strftime("%H:%M:%S")
    except:
        return str(ts)


def timestamp_to_date(ts):
    """Unix 毫秒时间戳转日期字符串"""
    if not ts:
        return None
    try:
        dt = datetime.fromtimestamp(ts / 1000, tz=CST)
        return dt.strftime("%m-%d %H:%M")
    except:
        return str(ts)


async def fetch():
    from pypetkitapi import PetKitClient
    from pypetkitapi.litter_container import Litter
    from pypetkitapi.feeder_container import Feeder
    from pypetkitapi.containers import Pet
    import os

    # 从环境变量读取凭证，如果没有则使用默认值（本地运行）
    username = os.environ.get("PETKIT_USERNAME", "19936288595")
    password = os.environ.get("PETKIT_PASSWORD", "chenjie521")

    async with aiohttp.ClientSession() as session:
        client = PetKitClient(
            username=username,
            password=password,
            timezone="Asia/Shanghai",
            region="cn",
            session=session
        )
        await client.init()

        result = {
            "updated_at": datetime.now(CST).isoformat(),
            "litter_box": {},
            "feeder": {},
            "pets": [],
        }

        data = await client.get_devices_data()

        # 猫砂盆
        for entity in data["devices"]:
            if isinstance(entity, Litter):
                result["litter_box"] = {
                    "name": entity.device_name,
                    "id": entity.id,
                    "box_full": entity.box_full,
                    "sand_percent": entity.sand_percent,
                    "sand_type": entity.sand_type,
                    "last_odor": entity.last_odor,
                    "pet_out_tips": entity.pet_out_tips,
                }
                break

        # 喂食器
        for entity in data["devices"]:
            if isinstance(entity, Feeder):
                result["feeder"] = {
                    "name": entity.device_name,
                    "id": entity.id,
                    "food": entity.food,
                    "eat_records": [],
                }
                # 进食记录
                try:
                    for rec in (entity.eat_records or []):
                        result["feeder"]["eat_records"].append({
                            "pet_id": rec.get("pet_id"),
                            "time": timestamp_to_time(rec.get("timestamp")),
                            "amount": rec.get("amount"),
                        })
                except:
                    pass
                break

        # 猫咪信息
        for entity in data["devices"]:
            if isinstance(entity, Pet):
                result["pets"].append({
                    "id": entity.id,
                    "name": entity.name,
                    "weight": entity.last_measured_weight,
                    "last_device": entity.last_device_used,
                    "last_litter_time": timestamp_to_date(entity.last_litter_usage),
                    "last_litter_duration": entity.last_duration_usage,
                })

        return result


def upload_to_github(filepath="petkit_data.json"):
    """上传到 GitHub Pages (仅本地运行使用)"""
    import base64
    import json
    import urllib.request
    import urllib.error
    import os

    TOKEN = os.environ.get("GITHUB_TOKEN", "")
    if not TOKEN:
        print("错误: 需要设置 GITHUB_TOKEN 环境变量")
        return
    
    OWNER = "cj309815680-byte"
    REPO = "period-tracker"
    FILE_PATH = filepath
    API_URL = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{FILE_PATH}"

    # 读取文件内容
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    # 获取现有sha
    sha = ""
    try:
        req = urllib.request.Request(API_URL, headers={
            "Authorization": f"token {TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "Python"
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
            sha = data.get("sha", "")
    except:
        pass

    # 上传
    payload = {"message": f"update {filepath}", "content": encoded, "branch": "main"}
    if sha:
        payload["sha"] = sha

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API_URL, data=data, headers={
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "Python"
    }, method="PUT")

    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"上传成功: {json.loads(r.read().decode('utf-8'))['content']['sha'][:12]}")
    except urllib.error.HTTPError as e:
        print(f"上传失败: HTTP {e.code}")


def main():
    import os
    print("正在获取小猫数据...")
    data = asyncio.run(fetch())
    with open("petkit_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已保存到 petkit_data.json")
    print(f"更新时间: {data['updated_at']}")
    print(f"猫砂盆: {data['litter_box']['name']} (砂量{data['litter_box']['sand_percent']}%)")
    print(f"喂食器: {data['feeder']['name']}")
    for pet in data['pets']:
        print(f"猫咪: {pet['name']} ({pet['weight']}g)")

    # 如果在 GitHub Actions 环境，不调用 upload_to_github（由 git commit 处理）
    # 本地运行时，上传到 GitHub
    if not os.environ.get("GITHUB_ACTIONS"):
        print("\n上传到 GitHub Pages...")
        upload_to_github()
        print("完成！")


if __name__ == "__main__":
    main()
