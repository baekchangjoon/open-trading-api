import logging
import os
import platform
import sys

from fastmcp import FastMCP

from module import setup_environment, EnvironmentMiddleware, EnvironmentConfig, setup_kis_config
from module.plugin import Database
from module.plugin.onepassword import resolve_op_references
from tools import *

logging.basicConfig(
    level=logging.DEBUG,  # DEBUG 이상 (DEBUG, INFO, WARNING...) 모두 출력
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)


def main():
    env = os.getenv("ENV", None)

    # 환경 설정
    logging.info("setup environment ...")
    env_config = setup_environment(env=env)

    # 1Password 비밀 주입 (.env 의 op:// 참조를 실제 값으로 치환)
    resolved = resolve_op_references()

    # KIS 설정 자동 생성 (템플릿 다운로드 + 값 덮어쓰기)
    # op:// 참조를 주입했다면 1Password를 원본으로 yaml을 강제 재생성한다.
    logging.info("setup KIS configuration ...")
    if not setup_kis_config(force_update=env == "live" or resolved > 0):
        logging.warning("KIS 설정 파일 생성에 실패했습니다. 수동으로 설정해주세요.")

    # 데이터베이스 초기화
    logging.info("setup database ...")
    db = None
    db_exists = False

    try:
        db = Database()
        db_exists = os.path.exists(os.path.join("configs/master", "master.db"))
        db.new(db_dir="configs/master")
        logging.info(f"📁 Available databases: {db.get_available_databases()}")
    except Exception as e:
        logging.error(f"❌ Database initialization failed: {e}")
        sys.exit(1)

    # MCP 서버 설정
    mcp_server = FastMCP(
        name="My Awesome MCP Server",
        instructions="This is a server for a specific project.",
        version="1.0.0",
    )

    # middleware
    mcp_server.add_middleware(EnvironmentMiddleware(environment=env_config))

    # tools 등록
    DomesticStockTool().register(mcp_server=mcp_server)
    DomesticFutureOptionTool().register(mcp_server=mcp_server)
    DomesticBondTool().register(mcp_server=mcp_server)
    OverseasStockTool().register(mcp_server=mcp_server)
    OverseasFutureOptionTool().register(mcp_server=mcp_server)
    ElwTool().register(mcp_server=mcp_server)
    EtfEtnTool().register(mcp_server=mcp_server)
    AuthTool().register(mcp_server=mcp_server)


    # MCP 서버 실행 방식 결정
    logging.info(f"🚀 MCP 서버를 {env_config.mcp_type} 모드로 시작합니다...")
    
    if env_config.mcp_type == "stdio":
        # stdio 모드 (기본값)
        logging.info("📝 stdio 모드로 MCP 서버를 시작합니다.")
        mcp_server.run(
            transport="stdio"
        )

    elif env_config.mcp_type == "sse":
        # HTTP 모드로 실행
        logging.info(f"🌐 Server Sent Event 모드로 MCP 서버를 시작합니다: {env_config.mcp_host}:{env_config.mcp_port}")
        mcp_server.run(
            transport="sse",
            host=env_config.mcp_host,
            port=env_config.mcp_port,
            path=env_config.mcp_path,
        )

    elif env_config.mcp_type == "streamable-http":
        # HTTP 모드로 실행
        logging.info(f"🌐 HTTP 모드로 MCP 서버를 시작합니다: {env_config.mcp_host}:{env_config.mcp_port}")
        mcp_server.run(
            transport="streamable-http",
            host=env_config.mcp_host,
            port=env_config.mcp_port,
            path=env_config.mcp_path,
        )
    else:
        logging.error(f"❌ 지원하지 않는 MCP_TYPE: {env_config.mcp_type}")
        sys.exit(1)
    

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("🛑 Application interrupted by user (Ctrl+C)")
