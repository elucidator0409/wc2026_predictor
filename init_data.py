import pandas as pd

# Đọc file matches.csv
matches_df = pd.read_csv('data/matches.csv')

# Thêm tham số utc=True để xử lý lẫn lộn múi giờ (Mixed timezones)
matches_df['kickoff_at'] = pd.to_datetime(matches_df['kickoff_at'], utc=True)

# Chuyển toàn bộ sang múi giờ Việt Nam (UTC+7)
matches_df['kickoff_at'] = matches_df['kickoff_at'].dt.tz_convert('Asia/Ho_Chi_Minh')

# Format lại cho đẹp: '2026-06-12 04:00'
matches_df['kickoff_at'] = matches_df['kickoff_at'].dt.strftime('%Y-%m-%d %H:%M')

# Ghi đè lại vào file
matches_df.to_csv('data/matches.csv', index=False)

print("✅ Đã chuyển đổi toàn bộ 104 trận đấu sang giờ Việt Nam thành công!")