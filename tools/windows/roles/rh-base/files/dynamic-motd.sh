# Dynamic Message of the Day with system information

main() {
  if is_interactive_shell; then
    print_pretty_hostname
    print_general_info
    print_filesystem_info
    print_nic_info
  fi
}

is_interactive_shell() {
  test -t 0
}

print_pretty_hostname() {
  figlet "$(hostname)"
}

print_general_info() {
  local distro load1 load5 load15 uptime \
    total_memory memory_usage total_swap swap_usage

  distro=$(grep '^PRETTY' /etc/os-release | sed 's/.*"\(.*\)"/\1/')

  # System load
  load1=$(awk '{print $1}' /proc/loadavg )
  load5=$(awk '{print $2}' /proc/loadavg )
  load15=$(awk '{print $3}' /proc/loadavg )

  # System uptime
  uptime=$(uptime --pretty | sed 's/up //')

  # Memory/swap usage in % (used/total*100)
  memory_usage=$(free | awk '/Mem:/  { printf("%3.2f%%", $3/$2*100) }')
  swap_usage=$(  free | awk '/Swap:/ { printf("%3.2f%%", $3/$2*100) }')

  # Total memory/swap in MiB
  total_memory=$(free -m | awk '/Mem:/  { printf("%s MiB", $2) }')
  total_swap=$(  free -m | awk '/Swap:/ { printf("%s MiB", $2) }')

  cat << _EOF_
System information as of $(date).

Distro/Kernel: ${distro} / $(uname --kernel-release)

System load:    ${load1}, ${load5}, ${load15}	Memory usage: ${memory_usage} of ${total_memory}
System uptime:  ${uptime}	Swap   usage: ${swap_usage} of ${total_swap}

_EOF_

}

print_filesystem_info() {
  df --si --local --print-type --total \
    --exclude-type=tmpfs --exclude-type=devtmpfs
}

print_nic_info() {
  local interfaces
  interfaces=$(ip --brief link | awk '{ print $1}')
  local mac
  local ip_info
  local ip4
  local ip6

  printf '\nInterface\tMAC Address\t\tIPv4 Address\t\tIPv6 Address\n'
  for nic in ${interfaces}; do
    mac=$(ip --brief link show dev "${nic}" | awk '{print $3}')
    ip_info=$(ip --brief address show dev "${nic}")
    ip4=$(awk '{print $3}' <<< "${ip_info}")
    ip6=$(awk '{print $4}' <<< "${ip_info}")

    printf '%s\t\t%s\t%s\t\t%s\t\n' "${nic}" "${mac}" "${ip4}" "${ip6}"
  done
}

main
