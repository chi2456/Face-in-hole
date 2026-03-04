"""
ミャクミャクなりきりARアプリ (Culture Festival Edition)

■ 開発のきっかけ
文化祭でみんなが楽しめる展示物を作りたいと考え、話題の「ミャクミャク」をテーマに選びました。
直近のインターンシップで学んだ「画像認識」を、ただの勉強で終わらせず
「実際に人が触れて楽しめる形」にしたくて開発した作品です。

■ こだわったポイント
1. 権利への配慮と工夫
   本物の画像は使えないため、生成AI（ChatGPT/Gemini）を活用して
   オリジナルのミャクミャク風アセットを自作しました。
2. 軽快な動き
   ラズパイのような非力なマシンでも動かせるよう、あえて重い3D処理を避け、
   2D画像を高速に合成する「軽くて驚かれる処理」を目指しました。
3. 生きているような演出
   ただ画像を貼るだけでなく、ランダムな「瞬き」や「人数による変身（自動色変え）」
   を盛り込み、触った人が驚く仕掛けを入れました。

■ 実装した主な機能
・AI顔認識：カメラに映った人の顔を自動で追いかけます。
・変身機能：1人なら通常、2人なら黒、3人以上なら金のミャクミャクに変身！
・アニメーション：ランダムなタイミングでパチパチ瞬きをします。
・背景合成：キー操作で、AIが生成したオシャレな背景フレームに切り替わります。

■ 操作ガイド
[0-9キー] 背景フレームの切り替え (9: ChatGPT画像, 8/7: Gemini画像)
[a/1/2/3]  顔モード切り替え (a: 人数連動 / 1: 通常 / 2: 黒 / 3: 金)
[pキー]    一時停止 / [qキー] 終了
"""

import cv2
import mediapipe as mp
import numpy as np
import pygame
import time
import random
import os

# --- 【修正ポイント】実行ファイルのディレクトリを基準にする設定 ---
# これにより、どのフォルダから実行しても画像や音声が読み込めます
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# フレーム画像のパス (BASE_DIRを結合)
PATH_FRAME_9 = os.path.join(BASE_DIR, "ChatGPT_Image_20251119_17_22_19.png")
PATH_FRAME_8 = os.path.join(BASE_DIR, "Gemini_Generated_Image_ggc4a1ggc4a1ggc4.png")
PATH_FRAME_7 = os.path.join(BASE_DIR, "Gemini_Generated_Image_goodkegoodkegood.png")

REQUEST_WIDTH = 1920
REQUEST_HEIGHT = 1080

# オーディオの初期化
pygame.mixer.init()
try:
    # パスを結合して指定
    sound_effect = pygame.mixer.Sound(os.path.join(BASE_DIR, "seen_change.mp3"))
except pygame.error:
    sound_effect = None

# MediaPipeの初期化
mp_face_detection = mp.solutions.face_detection
face_detection = mp_face_detection.FaceDetection(
    model_selection=0, min_detection_confidence=0.2)

# 顔画像の読み込み (すべて os.path.join で修正)
try:
    IMG_CENTER_OPEN = cv2.imread(os.path.join(BASE_DIR, 'myaku.png'))
    IMG_BLACK_OPEN = cv2.imread(os.path.join(BASE_DIR, 'myaku_black.png'))
    IMG_GOLD_OPEN = cv2.imread(os.path.join(BASE_DIR, 'myaku_gold.png'))

    if any(img is None for img in [IMG_CENTER_OPEN, IMG_BLACK_OPEN, IMG_GOLD_OPEN]):
        raise FileNotFoundError("必須の顔画像が見つかりません。")

    IMG_CENTER_CLOSED = cv2.imread(os.path.join(BASE_DIR, 'myaku_wink.png'))
    if IMG_CENTER_CLOSED is None: IMG_CENTER_CLOSED = IMG_CENTER_OPEN
    
    IMG_BLACK_CLOSED = cv2.imread(os.path.join(BASE_DIR, 'myaku_black_wink.png'))
    if IMG_BLACK_CLOSED is None: IMG_BLACK_CLOSED = IMG_BLACK_OPEN
    
    IMG_GOLD_CLOSED = cv2.imread(os.path.join(BASE_DIR, 'myaku_gold_wink.png'))
    if IMG_GOLD_CLOSED is None: IMG_GOLD_CLOSED = IMG_GOLD_OPEN

except Exception as e:
    print(f"画像読み込みエラー: {e}")
    exit()

# フレーム画像の読み込み関数
def load_frame(path):
    if os.path.exists(path):
        img = cv2.imread(path)
        if img is not None:
            return img
    print(f"警告: フレーム画像を読み込めませんでした -> {path}")
    return None

frames = {
    '9': load_frame(PATH_FRAME_9),
    '8': load_frame(PATH_FRAME_8),
    '7': load_frame(PATH_FRAME_7)
}
current_frame_source = None

# カメラ設定
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, REQUEST_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, REQUEST_HEIGHT)

window_name = 'MyakuMyaku App'
cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

# 状態管理変数
face_detected_prev_frame = False
last_blink_time = time.time()
blink_interval = random.uniform(2, 6)
blink_duration = 0.1
is_blinking = False
frame_mode = 'auto'
is_paused = False

# --- 【修正ポイント】直接実行時のみメインループを回す ---
if __name__ == '__main__':
    print("起動完了。操作方法はソースコード上部を参照してください。")

    while cap.isOpened():
        if not is_paused:
            success, image = cap.read()
            if not success: 
                continue

            image = cv2.flip(image, 1) # ミラー表示
            ih, iw, _ = image.shape
            
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = face_detection.process(image_rgb)
            annotated_image = image.copy()

            face_count = len(results.detections) if results.detections else 0

            # 効果音の再生
            face_detected_this_frame = bool(results.detections)
            if face_detected_this_frame and not face_detected_prev_frame:
                if sound_effect: sound_effect.play()
            face_detected_prev_frame = face_detected_this_frame
            
            # 瞬きの制御
            current_time = time.time()
            if is_blinking:
                if current_time - last_blink_time >= blink_duration:
                    is_blinking = False
                    last_blink_time = current_time
                    blink_interval = random.uniform(2, 6)
            else:
                if current_time - last_blink_time >= blink_interval:
                    is_blinking = True
                    last_blink_time = current_time

            # 顔の合成処理
            if results.detections:
                if frame_mode == 'auto':
                    if face_count >= 3:
                        base_open, base_closed = IMG_GOLD_OPEN, IMG_GOLD_CLOSED
                    elif face_count == 2:
                        base_open, base_closed = IMG_BLACK_OPEN, IMG_BLACK_CLOSED
                    else: 
                        base_open, base_closed = IMG_CENTER_OPEN, IMG_CENTER_CLOSED
                elif frame_mode == 'center':
                    base_open, base_closed = IMG_CENTER_OPEN, IMG_CENTER_CLOSED
                elif frame_mode == 'black':
                    base_open, base_closed = IMG_BLACK_OPEN, IMG_BLACK_CLOSED
                elif frame_mode == 'gold':
                    base_open, base_closed = IMG_GOLD_OPEN, IMG_GOLD_CLOSED
                
                img_to_use = base_closed if is_blinking else base_open
                
                for detection in results.detections:
                    bboxC = detection.location_data.relative_bounding_box
                    x_min, y_min = int(bboxC.xmin * iw), int(bboxC.ymin * ih)
                    w, h = int(bboxC.width * iw), int(bboxC.height * ih)

                    w_m, h_m = int(w * 2.3), int(h * 3.2)
                    if w_m <= 0 or h_m <= 0: continue
                    
                    img_resized = cv2.resize(img_to_use, (w_m, h_m))
                    x_pos = x_min - int((w_m - w) / 2)
                    y_pos = y_min - int((h_m - h) / 2) - 20
                    
                    x1, y1 = max(x_pos, 0), max(y_pos, 0)
                    x2, y2 = min(x_pos + w_m, iw), min(y_pos + h_m, ih)
                    
                    roi = annotated_image[y1:y2, x1:x2]
                    img_clipped = img_resized[(y1-y_pos):(y2-y_pos), (x1-x_pos):(x2-x_pos)]
                    
                    if img_clipped.shape[0] == 0 or img_clipped.shape[1] == 0: continue
                    
                    img_gray = cv2.cvtColor(img_clipped, cv2.COLOR_BGR2GRAY)
                    _, mask = cv2.threshold(img_gray, 251, 255, cv2.THRESH_BINARY)
                    mask_inv = cv2.bitwise_not(mask)
                    
                    if roi.shape[:2] != mask.shape: continue 
                    
                    fg = cv2.bitwise_and(img_clipped, img_clipped, mask=mask_inv)
                    bg = cv2.bitwise_and(roi, roi, mask=mask)
                    annotated_image[y1:y2, x1:x2] = cv2.add(fg, bg)

            # フレームの透過合成処理
            if current_frame_source is not None:
                try:
                    frame_resized = cv2.resize(current_frame_source, (iw, ih))
                    frame_gray = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)
                    
                    # 画素値50以下の暗部を透明化
                    _, mask_frame_exist = cv2.threshold(frame_gray, 50, 255, cv2.THRESH_BINARY)
                    mask_transparent = cv2.bitwise_not(mask_frame_exist)
                    
                    bg_base = cv2.bitwise_and(annotated_image, annotated_image, mask=mask_transparent)
                    fg_frame = cv2.bitwise_and(frame_resized, frame_resized, mask=mask_frame_exist)
                    final_output_image = cv2.add(bg_base, fg_frame)
                except Exception as e:
                    print(f"合成エラー: {e}")
                    final_output_image = annotated_image
            else:
                final_output_image = annotated_image

        if final_output_image is not None:
            cv2.imshow(window_name, final_output_image)

        # キー操作
        key = cv2.waitKey(5) & 0xFF
        if key == ord('q'): break
        elif key == ord('p'): is_paused = not is_paused
        elif key == ord('0'): current_frame_source = None
        elif key == ord('9') and frames['9'] is not None: current_frame_source = frames['9']
        elif key == ord('8') and frames['8'] is not None: current_frame_source = frames['8']
        elif key == ord('7') and frames['7'] is not None: current_frame_source = frames['7']
        elif key == ord('a'): frame_mode = 'auto'
        elif key == ord('1'): frame_mode = 'center'
        elif key == ord('2'): frame_mode = 'black'
        elif key == ord('3'): frame_mode = 'gold'

    cap.release()
    cv2.destroyAllWindows()
    pygame.mixer.quit()