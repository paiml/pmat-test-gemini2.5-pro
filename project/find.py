#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A Python script that mimics the Unix find command.
This script is a single file with no external dependencies.
"""
import os
import sys
import stat
import re
import fnmatch
from datetime import datetime, timedelta
import subprocess

class FindMimic:
    """
    A class that encapsulates the logic for mimicking the find command.
    """
    def __init__(self, args):
        self.paths, self.expression_tokens = self._parse_initial_args(args)
        self.pos = 0
        self.prune_paths = set()

        # Options with default values
        self.options = {
            'depth': False,
            'maxdepth': float('inf'),
            'mindepth': 0,
            'follow': False,
            'daystart': False,
        }

        # Pre-process options from the expression
        self._pre_process_options()

        # If no action is specified, -print is the default.
        if not any(arg in self._actions for arg in self.expression_tokens):
            self.expression_tokens.append('-print')

    def _pre_process_options(self):
        """Parses and removes global options from the expression list before evaluation."""
        new_tokens = []
        i = 0
        while i < len(self.expression_tokens):
            token = self.expression_tokens[i]
            if token == '-maxdepth':
                self.options['maxdepth'] = int(self.expression_tokens[i+1])
                i += 2
            elif token == '-mindepth':
                self.options['mindepth'] = int(self.expression_tokens[i+1])
                i += 2
            elif token == '-depth':
                self.options['depth'] = True
                i += 1
            elif token in ('-L', '-follow'):
                self.options['follow'] = True
                i += 1
            elif token == '-daystart':
                self.options['daystart'] = True
                i += 1
            elif token in ('-P', '-H', '-warn', '-nowarn', '-noleaf', '-xdev', '-mount'): # Acknowledge but ignore for simplicity
                i += 1
            else:
                new_tokens.append(token)
                i += 1
        self.expression_tokens = new_tokens


    def _parse_initial_args(self, args):
        """Separates initial paths from the expression."""
        paths = []
        expr_start_index = 0
        # Consume paths until an operator, parenthesis, or option is found
        for i, arg in enumerate(args):
            if arg.startswith('-') or arg in ['(', ')', '!', ',']:
                expr_start_index = i
                break
            paths.append(arg)
            expr_start_index = i + 1
        
        if not paths:
            paths = ['.']
        
        expression = args[expr_start_index:]
        return paths, expression

    def run(self):
        """Starts the find process."""
        for path in self.paths:
            if not os.path.exists(path):
                sys.stderr.write(f"find.py: '{path}': No such file or directory\n")
                continue
            self._walk(path)

    def _walk(self, start_path):
        """Walks the directory tree and applies the expression."""
        max_depth = self.options['maxdepth']
        min_depth = self.options['mindepth']
        follow_links = self.options['follow']
        use_depth_first = self.options['depth']

        # os.walk depth is relative to the start_path
        start_level = start_path.count(os.sep)

        if use_depth_first:
            # Post-order traversal
            for root, dirs, files in os.walk(start_path, topdown=False, followlinks=follow_links):
                current_level = root.count(os.sep) - start_level
                
                # Process files at the current level
                if current_level + 1 >= min_depth and current_level < max_depth:
                    for name in files:
                        path = os.path.join(root, name)
                        self.pos = 0
                        self._evaluate_expression(path)

                # Process directories at the current level
                if current_level >= min_depth and current_level < max_depth:
                     for name in dirs:
                        path = os.path.join(root, name)
                        self.pos = 0
                        self._evaluate_expression(path)
            
            # Process the start path itself
            if min_depth == 0:
                self.pos = 0
                self._evaluate_expression(start_path)

        else:
            # Pre-order traversal
            for root, dirs, files in os.walk(start_path, topdown=True, followlinks=follow_links):
                # Pruning logic
                dirs[:] = [d for d in dirs if os.path.join(root, d) not in self.prune_paths]

                current_level = root.count(os.sep) - start_level
                
                # Process the root of this walk iteration
                if current_level >= min_depth and current_level <= max_depth:
                    self.pos = 0
                    if self._evaluate_expression(root):
                        # If prune is triggered, it's handled by the expression evaluation
                        if root in self.prune_paths:
                            dirs[:] = [] # Clear dirs to stop descending
                            continue
                
                # Stop descending if maxdepth is reached
                if current_level >= max_depth:
                    dirs[:] = []

                # Process files and directories
                if current_level < max_depth:
                    for name in files:
                        if current_level + 1 >= min_depth:
                            path = os.path.join(root, name)
                            self.pos = 0
                            self._evaluate_expression(path)
                    for name in dirs:
                        if current_level + 1 >= min_depth:
                            path = os.path.join(root, name)
                            self.pos = 0
                            # Evaluate for potential pruning of subdirectories
                            if self._evaluate_expression(path) and path in self.prune_paths:
                                # This dir is pruned, but it's tricky to remove from dirs now
                                # The check at the start of the loop handles it
                                pass


    def _evaluate_expression(self, path):
        """Evaluates the expression for a given path using recursive descent."""
        self.pos = 0 # Reset for each path
        return self._parse_or_expr(path)

    # --- Recursive Descent Parser for find expressions ---
    def _peek(self):
        return self.expression_tokens[self.pos] if self.pos < len(self.expression_tokens) else None

    def _consume(self, expected=None):
        token = self._peek()
        if expected and token != expected:
            raise ValueError(f"Expected '{expected}' but found '{token}'")
        if token is not None:
            self.pos += 1
        return token

    def _parse_or_expr(self, path):
        """Parses -o / -or expressions."""
        left = self._parse_and_expr(path)
        while self._peek() in ('-o', '-or'):
            self._consume()
            # Short-circuit evaluation for 'or'
            if left:
                # We need to consume the right side of the expression without evaluating it
                self._parse_and_expr(path, evaluate=False)
                return True # The result of the OR is true
            else:
                right = self._parse_and_expr(path)
                left = left or right
        return left

    def _parse_and_expr(self, path, evaluate=True):
        """Parses -a / -and expressions (and implicit 'and')."""
        left = self._parse_not_expr(path, evaluate)
        while self._peek() is not None and self._peek() not in ('-o', '-or', ')', ','):
            if self._peek() in ('-a', '-and'):
                self._consume()
            # Short-circuit evaluation for 'and'
            if not evaluate or not left:
                self._parse_not_expr(path, evaluate=False)
                left = False
            else:
                right = self._parse_not_expr(path)
                left = left and right
        return left

    def _parse_not_expr(self, path, evaluate=True):
        """Parses ! / -not expressions."""
        if self._peek() in ('!', '-not'):
            self._consume()
            # If not evaluating, we still need to consume the sub-expression
            if not evaluate:
                self._parse_primary(path, evaluate=False)
                return False # Dummy value
            return not self._parse_primary(path)
        return self._parse_primary(path, evaluate)

    def _parse_primary(self, path, evaluate=True):
        """Parses primaries: parentheses, tests, and actions."""
        token = self._peek()
        if token == '(':
            self._consume()
            res = self._parse_or_expr(path)
            self._consume(')')
            return res
        
        if token in self._tests:
            self._consume()
            test_func = self._tests[token]
            num_args = self._get_num_args(token)
            args = [self._consume() for _ in range(num_args)]
            if evaluate:
                return test_func(self, path, *args)
            return True # For syntax-checking pass

        if token in self._actions:
            self._consume()
            action_func = self._actions[token]
            if token in ('-exec', '-ok', '-execdir', '-okdir'):
                args = []
                while self._peek() != ';':
                    arg = self._consume()
                    if arg is None: raise ValueError(f"Missing ';' for {token}")
                    args.append(arg)
                self._consume(';')
                if evaluate:
                    return action_func(self, path, args)
            else:
                num_args = self._get_num_args(token)
                args = [self._consume() for _ in range(num_args)]
                if evaluate:
                    return action_func(self, path, *args)
            return True # For syntax-checking pass

        if token is None:
            # This can happen with an implicit -a at the end
            return True

        raise ValueError(f"Unknown expression token: {token}")

    def _get_num_args(self, op):
        """Returns the number of arguments for a given operator."""
        one_arg_ops = [
            '-name', '-iname', '-path', '-ipath', '-regex', '-iregex', '-type', 
            '-perm', '-user', '-group', '-size', '-mtime', '-atime', '-ctime', 
            '-mmin', '-amin', '-cmin', '-links', '-inum', '-newer', '-anewer', '-cnewer'
        ]
        if op in one_arg_ops:
            return 1
        return 0

    # --- Helper methods for tests ---
    def _compare_num(self, val, target_str):
        sign = ''
        if target_str.startswith(('+', '-')):
            sign = target_str[0]
            target_str = target_str[1:]
        
        target = int(target_str)
        if sign == '+': return val > target
        if sign == '-': return val < target
        return val == target

    def _test_time(self, path, time_str, attr, unit_multiplier=86400):
        now = datetime.now()
        if self.options['daystart']:
            now = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        try:
            file_time = datetime.fromtimestamp(getattr(os.stat(path), attr))
        except FileNotFoundError:
            return False # File might have been deleted between os.walk and stat
            
        age_seconds = (now - file_time).total_seconds()
        age_units = age_seconds / unit_multiplier

        return self._compare_num(int(age_units), time_str)

    # --- Tests ---
    def _test_name(self, path, pattern): return fnmatch.fnmatch(os.path.basename(path), pattern)
    def _test_iname(self, path, pattern): return fnmatch.fnmatch(os.path.basename(path).lower(), pattern.lower())
    def _test_path(self, path, pattern): return fnmatch.fnmatch(path, pattern)
    def _test_ipath(self, path, pattern): return fnmatch.fnmatch(path.lower(), pattern.lower())
    def _test_regex(self, path, pattern): return re.search(pattern, path) is not None
    def _test_iregex(self, path, pattern): return re.search(pattern, path, re.IGNORECASE) is not None
    
    def _test_type(self, path, type_chars):
        try:
            mode = os.lstat(path).st_mode
        except FileNotFoundError:
            return False
        type_map = {
            'b': stat.S_ISBLK, 'c': stat.S_ISCHR, 'd': stat.S_ISDIR,
            'p': stat.S_ISFIFO, 'f': stat.S_ISREG, 'l': stat.S_ISLNK,
            's': stat.S_ISSOCK
        }
        for char in type_chars:
            if char in type_map and type_map[char](mode):
                return True
        return False

    def _test_perm(self, path, mode_str):
        try:
            file_mode = stat.S_IMODE(os.stat(path).st_mode)
        except FileNotFoundError:
            return False
            
        if mode_str.startswith('-'):
            # All of the permission bits in mode are set for the file.
            mode = int(mode_str[1:], 8)
            return (file_mode & mode) == mode
        if mode_str.startswith('/'):
            # Any of the permission bits in mode are set for the file.
            mode = int(mode_str[1:], 8)
            return (file_mode & mode) != 0
        # Exact match
        mode = int(mode_str, 8)
        return file_mode == mode

    def _test_size(self, path, size_str):
        unit_map = {'c': 1, 'w': 2, 'k': 1024, 'M': 1024**2, 'G': 1024**3}
        unit = size_str[-1]
        if unit in unit_map:
            target_val_str = size_str[:-1]
            multiplier = unit_map[unit]
        else:
            target_val_str = size_str
            multiplier = 512 # default blocks
        
        try:
            file_size = os.lstat(path).st_size
        except FileNotFoundError:
            return False
            
        target_val_str_numeric = target_val_str.lstrip('+-')
        
        target_blocks = int(target_val_str_numeric)
        
        sign = ''
        if target_val_str.startswith(('+', '-')):
            sign = target_val_str[0]

        # find's size calculation is based on rounding up to the next block
        file_blocks = (file_size + multiplier - 1) // multiplier

        if sign == '+': return file_blocks > target_blocks
        if sign == '-': return file_blocks < target_blocks
        return file_blocks == target_blocks

    def _test_mtime(self, path, n): return self._test_time(path, n, 'st_mtime')
    def _test_atime(self, path, n): return self._test_time(path, n, 'st_atime')
    def _test_ctime(self, path, n): return self._test_time(path, n, 'st_ctime')
    def _test_mmin(self, path, n): return self._test_time(path, n, 'st_mtime', 60)
    def _test_amin(self, path, n): return self._test_time(path, n, 'st_atime', 60)
    def _test_cmin(self, path, n): return self._test_time(path, n, 'st_ctime', 60)

    def _test_empty(self, path, *args):
        try:
            s = os.lstat(path)
            if stat.S_ISDIR(s.st_mode):
                return not os.listdir(path)
            return stat.S_ISREG(s.st_mode) and s.st_size == 0
        except (FileNotFoundError, OSError):
            return False

    def _test_links(self, path, n): 
        try:
            return self._compare_num(os.stat(path).st_nlink, n)
        except FileNotFoundError:
            return False
            
    def _test_inum(self, path, n): 
        try:
            return self._compare_num(os.stat(path).st_ino, n)
        except FileNotFoundError:
            return False

    def _test_newer(self, path, file, attr='st_mtime'):
        try:
            ref_time = getattr(os.stat(file), attr)
            return getattr(os.stat(path), attr) > ref_time
        except FileNotFoundError:
            sys.stderr.write(f"find.py: '{file}': No such file or directory\n")
            # This is a fatal error in GNU find
            sys.exit(1)
            
    def _test_anewer(self, path, file): return self._test_newer(path, file, 'st_atime')
    def _test_cnewer(self, path, file): return self._test_newer(path, file, 'st_ctime')

    def _test_readable(self, path, *args): return os.access(path, os.R_OK)
    def _test_writable(self, path, *args): return os.access(path, os.W_OK)
    def _test_executable(self, path, *args): return os.access(path, os.X_OK)

    def _test_true(self, path, *args): return True
    def _test_false(self, path, *args): return False

    # --- Actions ---
    def _action_print(self, path, *args):
        print(path)
        return True

    def _action_print0(self, path, *args):
        sys.stdout.write(path + '\0')
        sys.stdout.flush()
        return True

    def _action_ls(self, path, *args):
        try:
            st = os.lstat(path)
        except FileNotFoundError:
            return True # Don't fail if file disappears
            
        mode = stat.filemode(st.st_mode)
        nlink = st.st_nlink
        try:
            import pwd
            uid = pwd.getpwuid(st.st_uid).pw_name
        except (ImportError, KeyError):
            uid = st.st_uid
        try:
            import grp
            gid = grp.getgrgid(st.st_gid).gr_name
        except (ImportError, KeyError):
            gid = st.st_gid
        size = st.st_size
        mtime = datetime.fromtimestamp(st.st_mtime).strftime('%b %d %H:%M')
        
        # Format similar to `ls -dils`
        path_str = path
        if stat.S_ISLNK(st.st_mode):
            try:
                path_str += f" -> {os.readlink(path)}"
            except FileNotFoundError:
                path_str += " -> [broken]"

        print(f"{st.st_ino:6} {(st.st_blocks * 512) // 1024:4} {mode} {nlink:3} {uid:8} {gid:8} {size:8} {mtime} {path_str}")
        return True

    def _action_delete(self, path, *args):
        try:
            if os.path.isdir(path):
                os.rmdir(path)
            else:
                os.remove(path)
            return True
        except OSError as e:
            sys.stderr.write(f"find.py: cannot delete '{path}': {e.strerror}\n")
            return True # find continues after delete errors

    def _action_exec(self, path, command_parts, interactive=False, is_dir=False):
        # Note: This is a simplified implementation. It does not handle '{} +'.
        cmd = [p.replace('{}', path) for p in command_parts]
        
        if interactive:
            prompt = f"< {' '.join(cmd)} > ? "
            try:
                response = input(prompt)
                if response.lower() not in ('y', 'yes'):
                    return True
            except (EOFError, KeyboardInterrupt): # Handle non-interactive pipe or Ctrl+C
                print()
                return True

        try:
            cwd = os.path.dirname(path) if is_dir else None
            # For -execdir, the command is executed from the directory containing the file
            # and {} is replaced with the basename.
            if is_dir:
                cmd = [p.replace('{}', os.path.basename(path)) for p in command_parts]
                cwd = os.path.dirname(path)

            subprocess.run(cmd, check=False, cwd=cwd)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            # find does not terminate on exec errors
            sys.stderr.write(f"find.py: exec failed for {cmd[0]}: {e}\n")
        return True

    def _action_ok(self, path, command_parts):
        return self._action_exec(path, command_parts, interactive=True)

    def _action_execdir(self, path, command_parts):
        return self._action_exec(path, command_parts, is_dir=True)

    def _action_okdir(self, path, command_parts):
        return self._action_exec(path, command_parts, interactive=True, is_dir=True)

    def _action_prune(self, path, *args):
        # If the path is a directory, don't descend into it.
        if os.path.isdir(path):
            self.prune_paths.add(path)
        return True

    def _action_quit(self, path, *args):
        sys.exit(0)

    # --- Dispatch Tables ---
    _tests = {
        '-name': _test_name, '-iname': _test_iname, '-path': _test_path, '-wholename': _test_path,
        '-ipath': _test_ipath, '-iwholename': _test_ipath,
        '-regex': _test_regex, '-iregex': _test_iregex, '-type': _test_type, '-perm': _test_perm,
        '-size': _test_size, '-mtime': _test_mtime, '-atime': _test_atime, '-ctime': _test_ctime,
        '-mmin': _test_mmin, '-amin': _test_amin, '-cmin': _test_cmin, '-empty': _test_empty,
        '-links': _test_links, '-inum': _test_inum, '-newer': _test_newer, '-anewer': _test_anewer,
        '-cnewer': _test_cnewer, '-readable': _test_readable, '-writable': _test_writable,
        '-executable': _test_executable, '-true': _test_true, '-false': _test_false,
    }
    _actions = {
        '-print': _action_print, '-print0': _action_print0, '-ls': _action_ls,
        '-delete': _action_delete, '-exec': _action_exec, '-ok': _action_ok,
        '-execdir': _action_execdir, '-okdir': _action_okdir,
        '-prune': _action_prune, '-quit': _action_quit,
    }

def main():
    """
    Main function to run the find mimic script.
    """
    if len(sys.argv) == 1 or "--help" in sys.argv:
        print("Usage: find.py [-H] [-L] [-P] [path...] [expression]")
        print("A python mimic of the find command.")
        print("\nThis is a partial implementation and may not support all features or edge cases.")
        print("Supported options: -L, -P, -depth, -maxdepth, -mindepth, -daystart")
        print("Supported operators: -a, -and, -o, -or, !, -not, ( )")
        print("Supported tests: -name, -iname, -path, -type, -perm, -size, -mtime, -empty, ...")
        print("Supported actions: -print, -print0, -ls, -delete, -exec, -ok, -prune, -quit")
        return

    try:
        finder = FindMimic(sys.argv[1:])
        finder.run()
    except (ValueError, FileNotFoundError) as e:
        sys.stderr.write(f"find.py: {e}\n")
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        sys.exit(1)

if __name__ == "__main__":
    main()
