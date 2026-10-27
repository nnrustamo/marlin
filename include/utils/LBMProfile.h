// TEMPORARY profiling helper, not to be committed
#pragma once

#include <chrono>
#include <cstdlib>
#include <map>
#include <string>
#include <torch/torch.h>

namespace LBMProfile
{
struct Entry
{
  double seconds = 0.0;
  long calls = 0;
  std::size_t order = 0;
};

inline std::map<std::string, Entry> &
table()
{
  static std::map<std::string, Entry> t;
  return t;
}

inline bool &
active()
{
  static bool a = false;
  return a;
}

inline double
now()
{
  static const bool sync = std::getenv("MARLIN_PROFILE_SYNC") != nullptr;
  if (sync && torch::cuda::is_available())
    torch::cuda::synchronize();
  return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

inline void
add(const std::string & name, double dt)
{
  auto & t = table();
  auto it = t.find(name);
  if (it == t.end())
    it = t.emplace(name, Entry{0.0, 0, t.size()}).first;
  it->second.seconds += dt;
  it->second.calls++;
}
}

#include <algorithm>
#include <cstdio>
#include <vector>
namespace LBMProfile
{
/// print the table at program exit
struct ExitPrinter
{
  // construct the table first so it is destroyed after this printer
  ExitPrinter() { table(); }
  ~ExitPrinter()
  {
    std::vector<std::pair<std::string, Entry>> rows(table().begin(), table().end());
    std::sort(rows.begin(),
              rows.end(),
              [](auto & a, auto & b) { return a.second.order < b.second.order; });
    for (const auto & [name, e] : rows)
      std::printf("LBMPROFILE %-50s %10.6f s %6ld calls\n", name.c_str(), e.seconds, e.calls);
    std::fflush(stdout);
  }
};
inline ExitPrinter exit_printer;
}
