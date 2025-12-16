# -*- coding: utf-8 -*-
"""
数据分析与可视化工具
用于分析测距实验数据并生成统计图表
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager
import os
from datetime import datetime

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False


class DataAnalyzer:
    """数据分析器"""
    
    def __init__(self, output_dir='results'):
        """
        初始化分析器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = output_dir
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
    def load_data(self, filepath):
        """
        加载CSV数据文件
        
        Args:
            filepath: 文件路径
            
        Returns:
            DataFrame: 数据
        """
        return pd.read_csv(filepath, encoding='utf-8')
    
    def calculate_statistics(self, data, measured_col='测量距离', actual_col='实际距离'):
        """
        计算统计数据
        
        Args:
            data: DataFrame数据
            measured_col: 测量距离列名
            actual_col: 实际距离列名
            
        Returns:
            dict: 统计结果
        """
        if actual_col in data.columns:
            errors = np.abs(data[measured_col] - data[actual_col])
        else:
            errors = data[measured_col]
            
        return {
            'count': len(data),
            'mean': np.mean(data[measured_col]),
            'std': np.std(data[measured_col]),
            'min': np.min(data[measured_col]),
            'max': np.max(data[measured_col]),
            'error_mean': np.mean(errors) if actual_col in data.columns else None,
            'error_std': np.std(errors) if actual_col in data.columns else None
        }
    
    def plot_error_histogram(self, data, actual_distance, title='测距误差分布', 
                            measured_col='测量距离', save_path=None):
        """
        绘制误差直方图
        
        Args:
            data: DataFrame或数组
            actual_distance: 实际距离
            title: 图表标题
            measured_col: 测量距离列名
            save_path: 保存路径
        """
        if isinstance(data, pd.DataFrame):
            measurements = data[measured_col].values
        else:
            measurements = np.array(data)
            
        errors = measurements - actual_distance
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        n, bins, patches = ax.hist(errors, bins=20, edgecolor='black', alpha=0.7)
        
        # 添加统计信息
        mean_error = np.mean(errors)
        std_error = np.std(errors)
        
        ax.axvline(mean_error, color='red', linestyle='--', linewidth=2, 
                  label=f'均值: {mean_error:.4f}m')
        ax.axvline(mean_error + std_error, color='orange', linestyle=':', linewidth=2)
        ax.axvline(mean_error - std_error, color='orange', linestyle=':', linewidth=2,
                  label=f'标准差: {std_error:.4f}m')
        
        ax.set_xlabel('误差 (m)', fontsize=12)
        ax.set_ylabel('频次', fontsize=12)
        ax.set_title(f'{title}\n实际距离: {actual_distance}m, 样本数: {len(measurements)}', 
                    fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"图表已保存: {save_path}")
            
        plt.show()
        
    def plot_distance_comparison(self, results_dict, title='不同距离下的测距误差', save_path=None):
        """
        绘制不同距离下的误差对比图
        
        Args:
            results_dict: {实际距离: [测量值列表]} 字典
            title: 图表标题
            save_path: 保存路径
        """
        distances = sorted(results_dict.keys())
        means = []
        stds = []
        
        for d in distances:
            measurements = np.array(results_dict[d])
            errors = np.abs(measurements - d)
            means.append(np.mean(errors))
            stds.append(np.std(errors))
            
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        
        # 误差均值柱状图
        x = np.arange(len(distances))
        bars1 = ax1.bar(x, means, yerr=stds, capsize=5, color='steelblue', alpha=0.7)
        ax1.set_xlabel('实际距离 (m)', fontsize=12)
        ax1.set_ylabel('绝对误差均值 (m)', fontsize=12)
        ax1.set_title('不同距离下的测距误差均值', fontsize=14)
        ax1.set_xticks(x)
        ax1.set_xticklabels([f'{d}m' for d in distances])
        ax1.grid(True, alpha=0.3, axis='y')
        
        # 在柱子上标注数值
        for bar, mean, std in zip(bars1, means, stds):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + std + 0.01,
                    f'{mean:.3f}', ha='center', va='bottom', fontsize=10)
        
        # 误差方差柱状图
        bars2 = ax2.bar(x, stds, color='coral', alpha=0.7)
        ax2.set_xlabel('实际距离 (m)', fontsize=12)
        ax2.set_ylabel('绝对误差标准差 (m)', fontsize=12)
        ax2.set_title('不同距离下的测距误差标准差', fontsize=14)
        ax2.set_xticks(x)
        ax2.set_xticklabels([f'{d}m' for d in distances])
        ax2.grid(True, alpha=0.3, axis='y')
        
        for bar, std in zip(bars2, stds):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005,
                    f'{std:.3f}', ha='center', va='bottom', fontsize=10)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"图表已保存: {save_path}")
            
        plt.show()
        
    def plot_noise_comparison(self, results_dict, actual_distance=3.0, 
                             title='不同噪声环境下的测距误差', save_path=None):
        """
        绘制不同噪声环境下的误差对比图
        
        Args:
            results_dict: {环境名称: [测量值列表]} 字典
            actual_distance: 实际距离
            title: 图表标题
            save_path: 保存路径
        """
        environments = list(results_dict.keys())
        means = []
        stds = []
        
        for env in environments:
            measurements = np.array(results_dict[env])
            errors = np.abs(measurements - actual_distance)
            means.append(np.mean(errors))
            stds.append(np.std(errors))
            
        fig, ax = plt.subplots(figsize=(10, 6))
        
        x = np.arange(len(environments))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, means, width, label='误差均值', color='steelblue', alpha=0.7)
        bars2 = ax.bar(x + width/2, stds, width, label='误差标准差', color='coral', alpha=0.7)
        
        ax.set_xlabel('环境条件', fontsize=12)
        ax.set_ylabel('误差 (m)', fontsize=12)
        ax.set_title(f'{title}\n实际距离: {actual_distance}m', fontsize=14)
        ax.set_xticks(x)
        ax.set_xticklabels(environments)
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        
        # 标注数值
        for bar, val in zip(bars1, means):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                   f'{val:.3f}', ha='center', va='bottom', fontsize=9)
        for bar, val in zip(bars2, stds):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                   f'{val:.3f}', ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"图表已保存: {save_path}")
            
        plt.show()
        
    def plot_occlusion_comparison(self, results_dict, actual_distance=3.0,
                                  title='不同遮挡条件下的测距误差', save_path=None):
        """
        绘制不同遮挡条件下的误差对比图
        
        Args:
            results_dict: {遮挡条件: [测量值列表]} 字典
            actual_distance: 实际距离
            title: 图表标题
            save_path: 保存路径
        """
        # 使用与噪声对比相同的绘图方法
        self.plot_noise_comparison(results_dict, actual_distance, title, save_path)
        
    def plot_fps_over_time(self, fps_data, title='测距刷新率变化', save_path=None):
        """
        绘制FPS随时间变化图
        
        Args:
            fps_data: FPS数据列表或DataFrame
            title: 图表标题
            save_path: 保存路径
        """
        if isinstance(fps_data, pd.DataFrame):
            fps_values = fps_data['FPS'].values
        else:
            fps_values = np.array(fps_data)
            
        fig, ax = plt.subplots(figsize=(12, 5))
        
        ax.plot(fps_values, marker='o', markersize=3, linewidth=1, alpha=0.7)
        ax.axhline(np.mean(fps_values), color='red', linestyle='--', 
                  label=f'平均FPS: {np.mean(fps_values):.1f}')
        ax.axhline(1, color='green', linestyle=':', label='最低要求: 1 FPS')
        ax.axhline(20, color='orange', linestyle=':', label='满分标准: 20 FPS')
        
        ax.set_xlabel('测量次数', fontsize=12)
        ax.set_ylabel('FPS', fontsize=12)
        ax.set_title(title, fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"图表已保存: {save_path}")
            
        plt.show()
        
    def generate_summary_table(self, all_results, output_file='summary.csv'):
        """
        生成汇总表格
        
        Args:
            all_results: 所有实验结果的字典
            output_file: 输出文件名
            
        Returns:
            DataFrame: 汇总表格
        """
        rows = []
        
        for experiment, results in all_results.items():
            for condition, data in results.items():
                measurements = np.array(data['measurements'])
                actual = data.get('actual_distance', 0)
                errors = np.abs(measurements - actual) if actual else measurements
                
                rows.append({
                    '实验': experiment,
                    '条件': condition,
                    '实际距离(m)': actual,
                    '测量次数': len(measurements),
                    '测量均值(m)': np.mean(measurements),
                    '测量标准差(m)': np.std(measurements),
                    '误差均值(m)': np.mean(errors),
                    '误差标准差(m)': np.std(errors),
                    '最小误差(m)': np.min(errors),
                    '最大误差(m)': np.max(errors)
                })
                
        df = pd.DataFrame(rows)
        
        output_path = os.path.join(self.output_dir, output_file)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"汇总表格已保存: {output_path}")
        
        return df
    
    def generate_report_figures(self, distance_results, noise_results, 
                               occlusion_results, fps_data):
        """
        生成实验报告所需的所有图表
        
        Args:
            distance_results: 距离实验结果
            noise_results: 噪声实验结果
            occlusion_results: 遮挡实验结果
            fps_data: FPS数据
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 1. 距离实验
        self.plot_distance_comparison(
            distance_results,
            save_path=os.path.join(self.output_dir, f'distance_comparison_{timestamp}.png')
        )
        
        # 每个距离的误差直方图
        for dist, measurements in distance_results.items():
            self.plot_error_histogram(
                measurements, dist,
                title=f'测距误差分布 - {dist}m',
                save_path=os.path.join(self.output_dir, f'error_hist_{dist}m_{timestamp}.png')
            )
        
        # 2. 噪声实验
        self.plot_noise_comparison(
            noise_results,
            save_path=os.path.join(self.output_dir, f'noise_comparison_{timestamp}.png')
        )
        
        # 3. 遮挡实验
        self.plot_occlusion_comparison(
            occlusion_results,
            title='不同遮挡条件下的测距误差',
            save_path=os.path.join(self.output_dir, f'occlusion_comparison_{timestamp}.png')
        )
        
        # 4. FPS分析
        self.plot_fps_over_time(
            fps_data,
            save_path=os.path.join(self.output_dir, f'fps_analysis_{timestamp}.png')
        )
        
        print(f"\n所有图表已保存到 {self.output_dir} 目录")


def demo_analysis():
    """演示数据分析功能"""
    analyzer = DataAnalyzer()
    
    # 模拟数据 - 距离实验
    np.random.seed(42)
    distance_results = {
        0.5: 0.5 + np.random.normal(0, 0.02, 10),
        1.0: 1.0 + np.random.normal(0, 0.03, 10),
        2.0: 2.0 + np.random.normal(0, 0.05, 10),
        4.0: 4.0 + np.random.normal(0, 0.08, 10),
        7.0: 7.0 + np.random.normal(0, 0.12, 10),
    }
    
    # 模拟数据 - 噪声实验
    noise_results = {
        '安静环境': 3.0 + np.random.normal(0, 0.03, 10),
        '人说话环境': 3.0 + np.random.normal(0.05, 0.06, 10),
        '大音量音乐': 3.0 + np.random.normal(0.1, 0.1, 10),
    }
    
    # 模拟数据 - 遮挡实验
    occlusion_results = {
        '无遮挡': 3.0 + np.random.normal(0, 0.03, 10),
        '书籍遮挡': 3.0 + np.random.normal(0.02, 0.05, 10),
        '人体遮挡': 3.0 + np.random.normal(0.05, 0.08, 10),
    }
    
    # 模拟数据 - FPS
    fps_data = 15 + np.random.normal(0, 2, 100)
    
    # 生成所有图表
    analyzer.generate_report_figures(
        distance_results, noise_results, occlusion_results, fps_data
    )
    
    # 生成汇总表格
    all_results = {
        '距离实验': {
            f'{d}m': {'measurements': m.tolist(), 'actual_distance': d}
            for d, m in distance_results.items()
        },
        '噪声实验': {
            env: {'measurements': m.tolist(), 'actual_distance': 3.0}
            for env, m in noise_results.items()
        },
        '遮挡实验': {
            occ: {'measurements': m.tolist(), 'actual_distance': 3.0}
            for occ, m in occlusion_results.items()
        }
    }
    
    summary = analyzer.generate_summary_table(all_results)
    print("\n汇总统计:")
    print(summary.to_string(index=False))


if __name__ == '__main__':
    print("运行数据分析演示...")
    print("=" * 50)
    demo_analysis()
