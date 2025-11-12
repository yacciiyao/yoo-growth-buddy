# -*- coding: utf-8 -*-
# Author: yaccii.yao
# Date: 2025/2/25
# Description: 音频格式处理
import logging
import os
import subprocess
import time

from pydub import AudioSegment

logger = logging.getLogger("smart-buddy")


def convert_to_pcm(input_path, output_path):
    """
    将音频转换为 PCM 格式并保存
    :param input_path: 输入音频文件路径
    :param output_path: 输出音频文件路径
    :return: True表示成功，False表示失败
    """
    try:
        # 加载输入音频文件
        audio_source = AudioSegment.from_file(input_path)
        # 设置音频参数：16000Hz, 16bit深度, 单声道
        audio = audio_source.set_frame_rate(16000).set_sample_width(2).set_channels(1)
        # 保存为 WAV 格式，采用 PCM 编码
        audio.export(output_path, format="wav", codec="pcm_s16le")
        return True  # 转换成功
    except Exception as e:
        logger.error(f"convert_to_pcm failed: {e}")
        raise ValueError(f"转换为 pcm 格式失败: {e}")



import subprocess

def convert_to_wav(input_path, output_path):
    """
    使用 FFmpeg 将音频文件从 PCM 格式转换为 WAV 格式
    :param input_path: 输入音频文件路径
    :param output_path: 输出音频文件路径
    :return: True表示成功，False表示失败
    """
    try:
        # 构建FFmpeg命令
        command = [
            'ffmpeg',
            '-f', 's16le',         # 输入格式是 raw PCM（s16le 为 16-bit little-endian PCM）
            '-ar', '16000',        # 采样率：16000 Hz
            '-ac', '1',            # 单声道（mono）
            '-i', input_path,      # 输入文件路径
            '-t', '30',            # 设置最大时长（这里是 30 秒，可以调整）
            output_path            # 输出文件路径（WAV格式）
        ]

        # 执行FFmpeg命令
        subprocess.run(command, check=True)

        # 转换成功
        logger.info(f"成功将 {input_path} 转换为 {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        # 捕获并记录FFmpeg执行失败时的错误
        logger.error(f"FFmpeg转换失败: {e}")
        return False
    except Exception as e:
        # 捕获其他异常并记录
        logger.error(f"转换失败: {e}")
        return False


def convert_to_mp3(input_path, output_path):
    """
    将 PCM 音频转换为 MP3 格式并保存
    :param input_path: 输入音频文件路径
    :param output_path: 输出音频文件路径
    :return: True表示成功，False表示失败
    """
    try:
        # 这里使用ffmpeg命令来执行PCM到MP3的转换
        # 设置输入格式为s16le，采样率16kHz，单声道，输出为mp3格式
        command = [
            'ffmpeg', '-f', 's16le', '-ar', '16000', '-ac', '1', '-i', input_path,
            '-acodec', 'libmp3lame', '-ab', '192k', output_path
        ]

        # 执行命令
        subprocess.run(command, check=True)

        # 如果转换成功，返回True
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg 命令执行失败: {e}")
        return False
    except Exception as e:
        logger.error(f"转换失败: {e}")
        return False