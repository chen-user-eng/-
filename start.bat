@echo off
chcp 65001 >nul
echo ============================================================
echo   高频电商价格指数计算平台 - 一键启动脚本
echo ============================================================
echo.
echo [1/3] 检查Python环境...
python --version
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.x
    pause
    exit /b 1
)
echo.
echo [2/3] 检查数据是否已生成...
if not exist "data\ods\dt=2025-05-17\product_price.csv" (
    echo 数据未生成，开始生成模拟数据...
    python scripts/generate_data.py
    echo 数据生成完成！
) else (
    echo 数据已存在，跳过数据生成
)
echo.
echo [3/3] 检查指数是否已计算...
if not exist "data\ads\all_index.csv" (
    echo 指数未计算，开始计算价格指数...
    python scripts/process_pipeline.py
    echo 指数计算完成！
) else (
    echo 指数已计算，跳过计算
)
echo.
echo ============================================================
echo   启动可视化服务...
echo   访问地址: http://localhost:5000
echo   按 Ctrl+C 停止服务
echo ============================================================
echo.
python app.py
pause
