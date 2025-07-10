"""
Utility functions to postprocess results.
"""
import os
import re

from sys import argv

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

import scienceplots

plt.style.use('science')


def cu_perf_standalone(src_dir, case_name, dst_dir):
    """
    Read the results of the execution of the objective function for different
    computing units and plot.
    """
    total_times = {}
    for filename in os.listdir(src_dir):
        if not filename.startswith(f"cu") or case_name not in filename:
            continue
        cu = int(filename.split("_")[0][2:])
        df = pd.read_csv(os.path.join(src_dir, filename), index_col=0)
        total_times[cu] = df.sum().sum()
    # Plot
    total_times = dict(sorted(total_times.items()))
    plt.figure(figsize=(6.4, 4.8))
    plt.plot(total_times.keys(), total_times.values(), marker="o")
    plt.xscale("log")
    plt.xlabel("Computing Units")
    plt.ylabel("Total time (s)")
    plt.title("Total execution time of the feasibility objective function")
    plt.savefig(os.path.join(dst_dir, f"{case_name}_cu_performance.pdf"))
    plt.savefig(os.path.join(dst_dir, f"{case_name}_cu_performance.png"),
                dpi=300)
    plt.show()


def cu_perf_datagen(analysis_name, results_dir=None, compss_dir=None,
                    figures_dir=None):
    """
    Read the results of the execution of the whole datagen application for
    different computing units and plot the overall time comparison.
    """
    # Paths to directories
    if results_dir is None:
        results_dir = f'../../results/{analysis_name}'
    if compss_dir is None:
        compss_dir = f'../../logs/{analysis_name}'
    if figures_dir is None:
        figures_dir = f'../../figures/{analysis_name}'

    # Prepare lists for job_id, total_time, and n_cpus
    job_ids = []
    execution_time = []
    total_times_obj_func = []
    n_cases = []
    n_cpus_list = []
    times_per_func_call = []

    # Loop through subdirectories in the results directory
    for subdir in os.listdir(results_dir):
        subdir_path = os.path.join(results_dir, subdir)

        if os.path.isdir(subdir_path):
            # Extract job_id from the directory name
            match = re.search(r'slurm(\d+)_', subdir)
            if match:
                job_id = match.group(1)

                # Read the case_df_computing_times.csv file
                csv_file = os.path.join(subdir_path,
                                        'case_df_computing_times.csv')
                if os.path.exists(csv_file):
                    df = pd.read_csv(csv_file)

                    # Sum all elements ignoring the first column (index)
                    total_time = df.iloc[:, 1:].sum().sum()
                    n_case = len(df)
                    time_per_case = total_time / n_case

                    job_ids.append(job_id)
                    total_times_obj_func.append(total_time)
                    n_cases.append(n_case)
                    times_per_func_call.append(time_per_case)

                    # Look for the job_id folder in .COMPSs
                    job_dir = os.path.join(compss_dir, job_id)

                    # Get total execution time checking traces
                    trace_file = find_prv_file(job_dir)
                    if trace_file:
                        raw_time = search_total_time_in_trace(trace_file)
                        if raw_time:
                            # Raw time in nanoseconds
                            execution_time.append(raw_time / 1e9)

                    # Now search n_cpus
                    for root, dirs, files in os.walk(job_dir):
                        for file in files:
                            if file == 'job1_NEW.out':
                                out_file = os.path.join(root, file)
                                with open(out_file, 'r') as f:
                                    for line in f:
                                        # Find the line with "COMPUTING_UNITS:"
                                        if "COMPUTING_UNITS:" in line:
                                            n_cpus_match = re.search(
                                                r'COMPUTING_UNITS:\s+(\d+)',
                                                line)
                                            if n_cpus_match:
                                                n_cpus = int(
                                                    n_cpus_match.group(1))
                                                n_cpus_list.append(n_cpus)
                                                break
                        else:
                            continue
                        break

    # Save dataframe with results
    df = pd.DataFrame({
        'job ID': job_ids,
        'n_cpus': n_cpus_list,
        'n_cases': n_cases,
        'times per func call': times_per_func_call,
        'execution time': execution_time
    })
    df.sort_values(by='n_cpus', axis=0, ignore_index=True, inplace=True)

    # Other metrics
    parallel_efficiency = df['times per func call'][0] / (
            df['times per func call'] * df['n_cpus']) * 100
    df['parallel efficiency'] = parallel_efficiency
    effective_time_per_case = df['execution time'] / df['n_cases']
    df['effective time per case'] = effective_time_per_case

    # Ensure results directory for the figure exists
    os.makedirs(figures_dir, exist_ok=True)

    # Create plot of n_cpus vs total_time/n_cases
    fig, ax1 = plt.subplots(figsize=(8, 6))
    ax1.plot(df['n_cpus'], df['effective time per case'], 'bo-')
    ax1.set_xlabel('Number of CPUs')
    ax1.set_ylabel('Time per Case (s)', color='b')
    ax1.set_title(
        'Effective Time per Case vs Number of CPUs assigned to Obj. Func.')
    ax2 = ax1.twinx()
    ax2.plot(df['n_cpus'], df['n_cases'], 'gx--')
    ax2.set_ylabel('Number of cases', color='g')
    # Save the figure
    output_figure = os.path.join(figures_dir,
                                 'ncpus_vs_time_per_case')
    plt.show()
    fig.savefig(f"{output_figure}.png", dpi=300)
    fig.savefig(f"{output_figure}.pdf")

    # Create plot for parallel efficiency
    fig, ax1 = plt.subplots(figsize=(8, 6))
    ax1.plot(df['n_cpus'], df['parallel efficiency'], 'bo-')
    ax1.set_xlabel('Number of CPUs')
    ax1.set_ylabel('Parallel Efficiency (\%)')
    ax1.set_title('Parallel Efficiency')
    output_figure = os.path.join(figures_dir,
                                 'ncpus_vs_parallel_efficiency')
    plt.show()
    fig.savefig(f"{output_figure}.png", dpi=300)
    fig.savefig(f"{output_figure}.pdf")

    output_file = os.path.join(figures_dir, 'raw_data.csv')
    df.to_csv(output_file, index=False)


def find_prv_file(job_dir):
    # Loop through all files in the directory
    traces_dir = os.path.join(job_dir, 'trace')
    for file_name in os.listdir(traces_dir):
        # Check if the file has a .prv extension
        if file_name.endswith('.prv'):
            return os.path.join(traces_dir, file_name)
    return None


def search_total_time_in_trace(file_path):
    with open(file_path, 'r') as file:
        # Loop through each line in the file
        for line in file:
            # Use regex to find the number between ':' and '_ns'
            match = re.search(r':([0-9]+)_ns', line)
            if match:
                # Return the first occurrence of the number
                return int(match.group(1))
    return None


def create_gif_from_images(directory, output_file, gif_frame_count=20):
    from PIL import Image
    # Get all files in the directory
    files = os.listdir(directory)
    # Filter for image files and sort by creation timestamp
    images = [os.path.join(directory, f) for f in files if
              f.lower().endswith(('png', 'jpg', 'jpeg', 'bmp', 'tiff'))]
    images.sort(key=lambda x: os.path.getctime(x))

    # Select about gif_frame_count images evenly spaced
    total_images = len(images)
    if total_images < gif_frame_count:
        print("Not enough images to create the GIF.")
        return
    step = total_images // gif_frame_count
    selected_images = [images[i] for i in range(0, total_images, step)][
                      :gif_frame_count]

    # Open images and create frames
    frames = [Image.open(img) for img in selected_images]

    # Save frames as an animated GIF
    frames[0].save(
        output_file, save_all=True, append_images=frames[1:], optimize=True,
        duration=800, loop=0
    )
    print(f"GIF saved as {output_file}")


if __name__ == "__main__":
    name = 'cu_perf_datagen_1node'
    cu_perf_datagen(name)

    # # Parse arguments for src_dir and case_name
    # if len(argv) == 4:
    #     src_dir = argv[1]
    #     case_name = argv[2]
    #     dst_dir = argv[3]
    # else:
    #     print("Using default values for src_dir and case_name")
    #     src_dir = "../../performance_tests/results"
    #     case_name = "case_0_computing_times_seed17"
    #     dst_dir = "../../figures"
    #     print(f"src_dir: {src_dir}")
    #     print(f"case_name: {case_name}")
    # cu_perf_standalone(src_dir, case_name, dst_dir)

    # Animation example usage
    # input_directory = "../../results/figures_complex_2d_shape_holes"
    # output_gif = "output.gif"
    # create_gif_from_images(input_directory, output_gif)
