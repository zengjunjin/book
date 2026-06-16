import zipfile, os, shutil

zip_path = r"C:\Users\15116\Downloads\7a493-main.zip"
output_dir = r"C:\Users\15116\Desktop\book\backend\data"

os.makedirs(output_dir, exist_ok=True)

print(f"Opening: {zip_path}")
z = zipfile.ZipFile(zip_path)
print(f"Files in zip ({len(z.namelist())} total):")
for name in z.namelist():
    info = z.getinfo(name)
    size_str = f"{info.file_size / 1024:.1f} KB" if info.file_size > 1024 else f"{info.file_size} bytes"
    print(f"  {name} ({size_str})")

# 解压所有文件
print(f"\nExtracting to: {output_dir}")
z.extractall(output_dir)
z.close()

print("Extraction complete!")
print("\nFiles in data directory:")
for f in os.listdir(output_dir):
    fpath = os.path.join(output_dir, f)
    if os.path.isfile(fpath):
        size = os.path.getsize(fpath)
        print(f"  {f} ({size/1024:.1f} KB)")

# 检查是否有子目录
for root, dirs, files in os.walk(output_dir):
    for f in files:
        if f.endswith('.csv') and 'BX' in f.upper():
            print(f"\nFound Book-Crossing file: {os.path.join(root, f)}")
