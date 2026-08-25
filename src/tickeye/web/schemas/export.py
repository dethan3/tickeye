"""Versioned contract for portable user-data exports."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from tickeye.application.export_service import UserDataExport


class UserDataExportResponse(BaseModel):
    schema_version: Literal["tickeye-user-data-v1"] = "tickeye-user-data-v1"
    exported_at: datetime
    data: dict[str, Any]
    excluded_data: list[str]
    warnings: list[str]

    @classmethod
    def from_domain(cls, value: UserDataExport) -> "UserDataExportResponse":
        return cls(
            exported_at=value.exported_at,
            data=value.data,
            excluded_data=[
                "market_data_cache",
                "derived_risk_snapshots",
                "derived_policy_events",
                "derived_scenario_comparisons",
            ],
            warnings=[
                "该文件用于查看和迁移用户事实；当前版本尚未提供自动恢复导入。",
                "Scenario 的冻结输入会保留，以便解释既有比较；可重新取得的行情缓存不会重复导出。",
            ],
        )
