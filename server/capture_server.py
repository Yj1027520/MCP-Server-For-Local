from typing import Any
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import cv2
import random
import os

# 初始化 MCP 服务器
mcp = FastMCP("CameraCaptureServer")

load_dotenv()
image_save_path=os.getenv("IMAGE_SAVE_PATH")

@mcp.tool(description="使用本地摄像头拍照，返回拍照成功或失败的提示信息。无输入参数")
async def capture_camera_image() -> str:
    """
    使用本地摄像头进行拍照，并保存拍摄的图片。

    Returns:
        str: 拍照成功或失败的提示信息
    """
    try:
        # 打开摄像头
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "⚠️ 无法打开摄像头"

        print("DEBUG: 摄像头已打开")

        # 读取一帧图像
        ret, frame = cap.read()
        if not ret:
            cap.release()
            return "⚠️ 无法读取摄像头画面"

        print("DEBUG: 已读取摄像头画面")

        # 保存图片
        random_suffix = random.randint(10000, 99999)
        image_path = image_save_path + f"captured_image_{random_suffix}.jpg"
        cv2.imwrite(image_path, frame)
        print(f"DEBUG: 图片已保存至 {image_path}")

        # 释放摄像头资源
        cap.release()

        return f"成功拍摄并保存图片至 {image_path}"

    except Exception as e:
        return f"⚠️ 拍照失败: {str(e)}"

if __name__ == "__main__":
    print("DEBUG: Starting MCP CameraCaptureServer")
    mcp.run(transport="stdio")