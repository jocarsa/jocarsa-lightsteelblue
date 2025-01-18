import numpy as np
from PIL import Image
import cv2
import multiprocessing
import colorsys

def denoise_segment(segment_data):
    """
    Denoise a segment of the image.
    """
    segment, radius, tolerance, mix = segment_data
    height, width, channels = segment.shape
    result = segment.copy()

    if cv2 is not None:
        # OpenCV denoising
        bgr = cv2.cvtColor(segment, cv2.COLOR_RGB2BGR)
        h = float(tolerance)
        hColor = float(tolerance)
        search_window = max(3, radius*2+1)
        template_window = 7
        denoised = cv2.fastNlMeansDenoisingColored(
            bgr,
            None,
            h, hColor,
            template_window,
            search_window
        )
        rgb = cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB)
        # Blend with original
        out = (1.0 - mix)*segment.astype(np.float32) + mix*rgb.astype(np.float32)
        out = np.clip(out, 0, 255).astype(np.uint8)
        return out
    else:
        # Fallback to a simple average filter
        for y in range(height):
            for x in range(width):
                accum_l = 0.0
                count = 0
                r, g, b = segment[y, x, :3]
                h_main, l_main, s_main = colorsys.rgb_to_hls(r/255.0, g/255.0, b/255.0)
                for ny in range(max(0, y - radius), min(height, y + radius + 1)):
                    for nx in range(max(0, x - radius), min(width, x + radius + 1)):
                        rr, gg, bb = segment[ny, nx, :3]
                        h_n, l_n, s_n = colorsys.rgb_to_hls(rr/255.0, gg/255.0, bb/255.0)
                        if abs(l_n - l_main)*100 <= tolerance:
                            accum_l += l_n
                            count += 1
                if count > 0:
                    avg_l = accum_l / count
                    new_l = l_main + mix * (avg_l - l_main)
                    r_new, g_new, b_new = colorsys.hls_to_rgb(h_main, new_l, s_main)
                    result[y, x, 0] = int(r_new * 255)
                    result[y, x, 1] = int(g_new * 255)
                    result[y, x, 2] = int(b_new * 255)
        return result

def denoise_image(pil_img, radius=2, tolerance=10, mix=1.0):
    """
    Denoise the given PIL image using multiprocessing.
    """
    arr = np.array(pil_img)
    height, width = arr.shape[:2]
    num_cores = multiprocessing.cpu_count()
    # Split the image vertically into segments
    segments = np.array_split(arr, num_cores, axis=0)
    segment_data = [(segment, radius, tolerance, mix) for segment in segments]

    with multiprocessing.Pool(processes=num_cores) as pool:
        denoised_segments = pool.map(denoise_segment, segment_data)

    denoised_arr = np.vstack(denoised_segments)
    return Image.fromarray(denoised_arr, mode=pil_img.mode)
