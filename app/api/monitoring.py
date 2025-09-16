"""
监控API - 提供性能指标和系统状态查询
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

from app.core.database import redis_client
from app.core.security import get_current_active_user
from app.models.user import User, MembershipType
from app.middleware.performance_monitor import (
    metrics_collector, 
    performance_analyzer,
    PerformanceAnalyzer
)

router = APIRouter()

@router.get("/metrics/overview")
async def get_metrics_overview(
    current_user: User = Depends(get_current_active_user)
):
    """获取系统指标概览"""
    try:
        overall_stats = metrics_collector.get_overall_stats()
        return {
            "status": "success",
            "data": overall_stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取指标失败: {str(e)}")

@router.get("/metrics/performance-report")
async def get_performance_report(
    current_user: User = Depends(get_current_active_user)
):
    """获取性能分析报告"""
    # 只有管理员或企业用户可以查看详细报告
    if (current_user.membership.membership_type not in [MembershipType.ENTERPRISE] 
        and not getattr(current_user, 'is_admin', False)):
        raise HTTPException(status_code=403, detail="权限不足")
    
    try:
        report = await performance_analyzer.get_performance_report()
        return {
            "status": "success",
            "data": report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成报告失败: {str(e)}")

@router.get("/metrics/endpoint-stats")
async def get_endpoint_stats(
    endpoint: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    """获取端点统计信息"""
    try:
        if endpoint:
            stats = metrics_collector.get_endpoint_stats(endpoint)
            return {
                "status": "success",
                "data": {
                    "endpoint": endpoint,
                    "stats": stats
                }
            }
        else:
            # 返回所有端点的统计
            all_stats = {}
            for ep in metrics_collector.request_counts.keys():
                all_stats[ep] = metrics_collector.get_endpoint_stats(ep)
            
            return {
                "status": "success",
                "data": all_stats
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取端点统计失败: {str(e)}")

@router.get("/metrics/slow-endpoints")
async def get_slow_endpoints(
    threshold_ms: float = 1000,
    limit: int = 10,
    current_user: User = Depends(get_current_active_user)
):
    """获取慢端点列表"""
    try:
        slow_endpoints = await PerformanceAnalyzer.get_slow_endpoints(threshold_ms, limit)
        return {
            "status": "success",
            "data": slow_endpoints,
            "threshold_ms": threshold_ms
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取慢端点失败: {str(e)}")

@router.get("/metrics/error-endpoints")
async def get_error_endpoints(
    min_error_rate: float = 5.0,
    limit: int = 10,
    current_user: User = Depends(get_current_active_user)
):
    """获取高错误率端点列表"""
    try:
        error_endpoints = await PerformanceAnalyzer.get_error_endpoints(min_error_rate, limit)
        return {
            "status": "success",
            "data": error_endpoints,
            "min_error_rate": min_error_rate
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取错误端点失败: {str(e)}")

@router.get("/metrics/business-metrics")
async def get_business_metrics(
    days: int = 7,
    current_user: User = Depends(get_current_active_user)
):
    """获取业务指标"""
    try:
        business_data = []
        
        # 获取最近N天的业务指标
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            daily_key = f"business_metrics:{date}"
            
            try:
                daily_metrics = redis_client.hgetall(daily_key)
                if daily_metrics:
                    # 转换为整数
                    daily_metrics = {k: int(v) for k, v in daily_metrics.items()}
                    daily_metrics['date'] = date
                    business_data.append(daily_metrics)
                else:
                    # 如果没有数据，填充0
                    business_data.append({
                        'date': date,
                        'literature_processed': 0,
                        'ai_requests': 0,
                        'user_sessions': 0,
                        'projects_created': 0,
                        'exports_completed': 0
                    })
            except Exception as e:
                logger.warning(f"获取日期 {date} 的业务指标失败: {e}")
                continue
        
        # 按日期排序
        business_data.sort(key=lambda x: x['date'])
        
        return {
            "status": "success",
            "data": business_data,
            "days": days
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取业务指标失败: {str(e)}")

@router.get("/metrics/system-health")
async def get_system_health(
    current_user: User = Depends(get_current_active_user)
):
    """获取系统健康状态"""
    try:
        # 获取最新的系统指标
        system_metrics = metrics_collector.system_metrics
        overall_stats = metrics_collector.get_overall_stats()
        
        # 计算健康分数
        health_score = 100
        issues = []
        
        # CPU使用率检查
        cpu_percent = system_metrics.get('cpu_percent', 0)
        if cpu_percent > 90:
            health_score -= 20
            issues.append(f"CPU使用率过高: {cpu_percent:.1f}%")
        elif cpu_percent > 70:
            health_score -= 10
            issues.append(f"CPU使用率较高: {cpu_percent:.1f}%")
        
        # 内存使用率检查
        memory_percent = system_metrics.get('memory_percent', 0)
        if memory_percent > 90:
            health_score -= 20
            issues.append(f"内存使用率过高: {memory_percent:.1f}%")
        elif memory_percent > 70:
            health_score -= 10
            issues.append(f"内存使用率较高: {memory_percent:.1f}%")
        
        # API错误率检查
        error_rate = overall_stats.get('error_rate', 0)
        if error_rate > 10:
            health_score -= 30
            issues.append(f"API错误率过高: {error_rate:.2f}%")
        elif error_rate > 5:
            health_score -= 15
            issues.append(f"API错误率较高: {error_rate:.2f}%")
        
        # 响应时间检查
        avg_response_time = overall_stats.get('avg_response_time', 0)
        if avg_response_time > 2000:
            health_score -= 25
            issues.append(f"平均响应时间过长: {avg_response_time:.0f}ms")
        elif avg_response_time > 1000:
            health_score -= 10
            issues.append(f"平均响应时间较长: {avg_response_time:.0f}ms")
        
        # 确定健康状态
        if health_score >= 90:
            status = "healthy"
            color = "green"
        elif health_score >= 70:
            status = "warning"
            color = "yellow"
        else:
            status = "critical"
            color = "red"
        
        return {
            "status": "success",
            "data": {
                "health_score": max(0, health_score),
                "status": status,
                "color": color,
                "issues": issues,
                "system_metrics": system_metrics,
                "api_metrics": {
                    "total_requests": overall_stats.get('total_requests', 0),
                    "error_rate": error_rate,
                    "avg_response_time": avg_response_time
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取系统健康状态失败: {str(e)}")

@router.post("/metrics/record-business-event")
async def record_business_event(
    event_type: str,
    value: int = 1,
    current_user: User = Depends(get_current_active_user)
):
    """记录业务事件（供内部调用）"""
    try:
        metrics_collector.record_business_metric(event_type, value)
        return {
            "status": "success",
            "message": f"已记录事件 {event_type}: {value}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"记录业务事件失败: {str(e)}")

@router.get("/metrics/alerts")
async def get_performance_alerts(
    current_user: User = Depends(get_current_active_user)
):
    """获取性能告警"""
    if (current_user.membership.membership_type not in [MembershipType.ENTERPRISE] 
        and not getattr(current_user, 'is_admin', False)):
        raise HTTPException(status_code=403, detail="权限不足")
    
    try:
        alerts = []
        overall_stats = metrics_collector.get_overall_stats()
        system_metrics = metrics_collector.system_metrics
        
        # CPU告警
        cpu_percent = system_metrics.get('cpu_percent', 0)
        if cpu_percent > 85:
            alerts.append({
                "type": "system",
                "level": "critical" if cpu_percent > 95 else "warning",
                "message": f"CPU使用率过高: {cpu_percent:.1f}%",
                "value": cpu_percent,
                "threshold": 85,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        # 内存告警
        memory_percent = system_metrics.get('memory_percent', 0)
        if memory_percent > 85:
            alerts.append({
                "type": "system",
                "level": "critical" if memory_percent > 95 else "warning",
                "message": f"内存使用率过高: {memory_percent:.1f}%",
                "value": memory_percent,
                "threshold": 85,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        # API错误率告警
        error_rate = overall_stats.get('error_rate', 0)
        if error_rate > 5:
            alerts.append({
                "type": "api",
                "level": "critical" if error_rate > 15 else "warning",
                "message": f"API错误率过高: {error_rate:.2f}%",
                "value": error_rate,
                "threshold": 5,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        # 响应时间告警
        avg_response_time = overall_stats.get('avg_response_time', 0)
        if avg_response_time > 1500:
            alerts.append({
                "type": "performance",
                "level": "critical" if avg_response_time > 3000 else "warning",
                "message": f"平均响应时间过长: {avg_response_time:.0f}ms",
                "value": avg_response_time,
                "threshold": 1500,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        return {
            "status": "success",
            "data": alerts,
            "alert_count": len(alerts)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取告警信息失败: {str(e)}")