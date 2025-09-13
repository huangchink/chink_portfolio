# interleave16_print.py
# 在終端機印出 4x4 空間交錯(=16 banks) 的 bank 對應與打包結果
# 不需任何外部套件

def bank_id(y, x, br=4, bc=4):
    """回傳 0..15 的 bank 編號；顯示時再 +1 變 1..16。"""
    return (y % br) * bc + (x % bc)

def make_test_image(H, W):
    """做一張容易檢查的灰階 ramp 影像(0..255 循環)。回傳 HxW 的 list[list[int]]。"""
    img = []
    v = 0
    for y in range(H):
        row = []
        for x in range(W):
            row.append(v & 0xFF)
            v += 1
        img.append(row)
    return img

def pack_to_16banks(img, br=4, bc=4):
    """把 HxW(灰階) 影像依 4x4 空間交錯打包到 16 個 bank。
       回傳 banks(list[list[int]]) 以及 (y,x)->(bank,bank_addr) 的 map(list)。"""
    H, W = len(img), len(img[0])
    banks = [[] for _ in range(br*bc)]
    counts = [0]*(br*bc)
    addr_map = []  # (y,x,bank,bank_addr)

    for y in range(H):
        for x in range(W):
            b = bank_id(y, x, br, bc)
            addr_map.append((y, x, b, counts[b]))
            banks[b].append(img[y][x])
            counts[b] += 1
    return banks, addr_map

def reconstruct_from_16banks(banks, H, W, br=4, bc=4):
    """把 16 個 bank 依同樣走訪規則還原回 HxW(灰階) 影像，用來驗證。"""
    img = [[0]*W for _ in range(H)]
    read_ptr = [0]*len(banks)
    for y in range(H):
        for x in range(W):
            b = bank_id(y, x, br, bc)
            img[y][x] = banks[b][read_ptr[b]]
            read_ptr[b] += 1
    return img

def print_bank_layout(H, W, br=4, bc=4):
    """印出與你圖一樣的 1..16 bank 佈局（逐列列印）。"""
    print(f"\n[Bank layout {br}x{bc} over image {H}x{W} (numbers 1..{br*bc})]")
    for y in range(H):
        line = []
        for x in range(W):
            line.append(f"{bank_id(y,x,br,bc)+1:2d}")
        print(" ".join(line))
    print()

def main():
    # 你可以改這裡尺寸
    H, W = 8, 16  # 影像高寬
    img = make_test_image(H, W)

    print_bank_layout(H, W, 4, 4)

    banks, addr_map = pack_to_16banks(img, 4, 4)

    # 印出前 40 筆 (y,x)-> bank/addr 對應，方便檢查
    print("[(y,x) -> bank, bank_addr] preview (first 40):")
    for y, x, b, a in addr_map[:40]:
        print(f"  ({y:2d},{x:2d}) -> bank {b+1:2d}, addr {a}")

    # 各 bank 長度與前幾個元素
    print("\n[Per-bank packed length & head preview]")
    for i, data in enumerate(banks):
        head = ", ".join(str(v) for v in data[:8])
        print(f"  bank {i+1:2d}: len={len(data):4d} | {head} ...")

    # 驗證還原
    recon = reconstruct_from_16banks(banks, H, W, 4, 4)
    ok = (recon == img)
    print(f"\nReconstruct OK? {ok}")

if __name__ == "__main__":
    main()
