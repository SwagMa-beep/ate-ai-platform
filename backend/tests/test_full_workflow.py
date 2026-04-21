"""
API测试
测试HTTP接口
"""
import os
import requests
import time
from pathlib import Path
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="integration workflow requires a running backend service and sample PDF files",
)

API_BASE = "http://localhost:8000/api/v1/testplan"


def test_api_workflow():
    """测试完整API流程"""

    print("\n" + "=" * 60)
    print("开始API完整流程测试")
    print("=" * 60 + "\n")

    # Step 1: 检查服务是否运行
    try:
        response = requests.get("http://localhost:8000/health", timeout=2)
        print(f"✅ 服务运行中: {response.json()['status']}")
    except requests.exceptions.RequestException:
        print("❌ 服务未启动，请先运行:")
        print("   cd backend")
        print("   uvicorn app.main:app --reload")
        return False

    # Step 2: 上传PDF
    print("\n📤 Step 1: 上传PDF...")
    test_pdf = Path("../data/raw/LM317_datasheet.pdf")

    if not test_pdf.exists():
        print(f"❌ 测试文件不存在: {test_pdf}")
        return False

    with test_pdf.open("rb") as f:
        response = requests.post(
            f"{API_BASE}/upload",
            files={"file": ("LM317.pdf", f, "application/pdf")}
        )

    if response.status_code != 200:
        print(f"❌ 上传失败: {response.text}")
        return False

    upload_result = response.json()
    file_id = upload_result['data']['file_id']
    print(f"✅ 上传成功，文件ID: {file_id}")
    print(f"   文件大小: {upload_result['data']['size_mb']} MB")

    # Step 3: 提取参数
    print(f"\n🤖 Step 2: 提取参数（这可能需要30-60秒）...")

    response = requests.post(
        f"{API_BASE}/extract",
        params={
            "file_id": file_id,
            "pages": "3-9",
            "max_workers": 3
        },
        timeout=300  # 5分钟超时
    )

    if response.status_code != 200:
        print(f"❌ 提取失败: {response.text}")
        return False

    extract_result = response.json()
    print(f"✅ 提取成功")
    print(f"   芯片: {extract_result['data']['chip_name']}")
    print(f"   总参数: {extract_result['data']['statistics']['total']}")
    print(f"   A类: {extract_result['data']['statistics']['A_class']}")
    print(f"   B类: {extract_result['data']['statistics']['B_class']}")
    print(f"   C类: {extract_result['data']['statistics']['C_class']}")

    # Step 4: 下载Excel
    print(f"\n📥 Step 3: 下载Excel...")
    response = requests.get(
        f"{API_BASE}/download/{file_id}/excel",
        stream=True
    )

    if response.status_code != 200:
        print(f"❌ 下载失败: {response.text}")
        return False

    output_path = Path("../data/test_api_output.xlsx")
    with output_path.open("wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    print(f"✅ Excel已下载: {output_path.absolute()}")
    print(f"   文件大小: {output_path.stat().st_size / 1024:.1f} KB")

    # Step 5: 列出文件
    print(f"\n📋 Step 4: 列出所有文件...")
    response = requests.get(f"{API_BASE}/list")

    if response.status_code == 200:
        files = response.json()['data']
        print(f"✅ 共有 {files['total']} 个文件")
        for f in files['files'][:3]:
            print(f"   - {f['filename']} ({f['size_mb']} MB)")

    print("\n" + "=" * 60)
    print("🎉 所有测试通过！")
    print("=" * 60 + "\n")

    return True


def test_async_workflow():
    """测试异步API"""
    print("\n" + "=" * 60)
    print("测试异步提取API")
    print("=" * 60 + "\n")

    # 上传文件
    test_pdf = Path("../data/raw/LM317_datasheet.pdf")
    with test_pdf.open("rb") as f:
        response = requests.post(
            f"{API_BASE}/upload",
            files={"file": f}
        )
    file_id = response.json()['data']['file_id']
    print(f"✅ 文件已上传: {file_id}")

    # 提交异步任务
    print(f"\n🚀 提交异步任务...")
    response = requests.post(
        f"{API_BASE}/extract-async",
        params={"file_id": file_id, "pages": "3-9"}
    )

    task_id = response.json()['data']['task_id']
    print(f"✅ 任务已提交: {task_id}")

    # 轮询状态
    print(f"\n⏳ 等待任务完成...")
    max_attempts = 60
    for i in range(max_attempts):
        response = requests.get(f"{API_BASE}/status/{task_id}")
        status_data = response.json()['data']

        status = status_data['status']
        message = status_data.get('message', '')

        print(f"  [{i + 1}/{max_attempts}] {status}: {message}")

        if status in ['completed', 'failed']:
            break

        time.sleep(2)

    if status == 'completed':
        print(f"\n✅ 异步任务完成！")
        result = status_data.get('result', {})
        print(f"   总参数: {result.get('total_params')}")
        return True
    else:
        print(f"\n❌ 任务失败")
        return False


if __name__ == "__main__":
    # 测试同步API
    success = test_api_workflow()

    # 测试异步API（可选）
    if success:
        print("\n是否测试异步API？(y/n): ", end="")
        choice = input().lower()
        if choice == 'y':
            test_async_workflow()
